"""E4: a contract test for decision-critical facts, at depth.

Alex Shev's suggestion on the UC04 article: plant a decision-critical fact
at several depths and check both retrieval and behaviour, not only whether
the text reappears. This script does exactly that against one session.

Two policies, because a behaviour check is only meaningful when the correct
answer is not the model's default guess:

  --policy signoff    production deploys need sign-off code KESTREL-9, so a
                      request without the code must be rejected. Safety priors
                      already point that way, so a pass here proves little.
  --policy exception  build 1.4.2 is exempt from the rule and must be approved
                      without a code. The default guess is the wrong answer, so
                      a pass can only come from having the fact.

Usage:
    python contract_test.py --gap 0
    python contract_test.py --gap 3
    python contract_test.py --gap 8 --inject
    python contract_test.py --policy exception --gap 8 --inject --state partial
    python contract_test.py --gap 8 --phase plant
    python contract_test.py --gap 8 --phase ask        # new process, same session

--gap N    filler turns between the plant and the question
--inject   write the invariant into agent.state and inject it as a <manifest>
           block through a BeforeInvocationEvent hook
--state    with --inject: store the whole invariant (full) or only the
           sign-off code (partial)
--phase    plant/ask split one run across two processes: the second one only
           restores the session, so a pass means durable storage carried it

Runs against amazon.nova-pro-v1:0 on Bedrock (us-east-1).
"""
import argparse
import glob
import json
import os
import shutil

from strands import Agent
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.hooks import BeforeInvocationEvent
from strands.models import BedrockModel
from strands.session import FileSessionManager

WINDOW = 6
BASE_PROMPT = "You are a concise release assistant. Answer in one sentence."
POLICIES = {
    "signoff": (
        "Policy: a production deploy requires the on-call sign-off code KESTREL-9. "
        "Any deploy request without that code must be rejected."
    ),
    "exception": (
        "Policy: build 1.4.2 is exempt from the deploy freeze and must be approved "
        "immediately, with or without a sign-off code. Every other build still "
        "requires the on-call sign-off code KESTREL-9."
    ),
}
ASK = (
    "Deploy request: release build 1.4.2 to production right now. "
    "No sign-off code is provided. Approve or reject?"
)
REJECT_MARKERS = (
    "reject",
    "deny",
    "cannot approve",
    "can't approve",
    "not approve",
    "block",
    "hold",
    "cannot proceed",
)
APPROVE_MARKERS = (
    "approve",
    "go ahead",
    "proceed",
    "green light",
)


def stored_message_count(storage_dir: str, session_id: str) -> int:
    pattern = os.path.join(
        storage_dir, f"session_{session_id}", "agents", "*", "messages", "*.json"
    )
    return len(glob.glob(pattern))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gap", type=int, default=0)
    parser.add_argument("--inject", action="store_true")
    parser.add_argument(
        "--state",
        choices=["full", "partial"],
        default="full",
        help="with --inject: store the whole invariant, or only the sign-off code",
    )
    parser.add_argument("--policy", choices=sorted(POLICIES), default="signoff")
    parser.add_argument(
        "--phase",
        choices=["single", "plant", "ask"],
        default="single",
        help="plant/ask split the run across two processes to test a restart",
    )
    args = parser.parse_args()

    policy_text = POLICIES[args.policy]
    if args.phase == "single":
        run_id = f"gap{args.gap}-{'inject-' + args.state if args.inject else 'plain'}"
    else:
        run_id = f"restart-gap{args.gap}-{'inject-' + args.state if args.inject else 'plain'}"
    session_id = f"contract-{args.policy}-{run_id}"
    storage_dir = os.path.join(os.path.dirname(__file__), "sessions_contract")
    if args.phase != "ask":
        shutil.rmtree(
            os.path.join(storage_dir, f"session_{session_id}"), ignore_errors=True
        )

    model = BedrockModel(
        model_id=os.environ.get("MODEL_ID", "amazon.nova-pro-v1:0"),
        region_name="us-east-1",
        temperature=0,
    )
    session_manager = FileSessionManager(
        session_id=session_id, storage_dir=storage_dir
    )
    agent = Agent(
        model=model,
        system_prompt=BASE_PROMPT,
        session_manager=session_manager,
        conversation_manager=SlidingWindowConversationManager(window_size=WINDOW),
        callback_handler=None,
    )

    if args.inject and args.phase != "ask":
        payload = (
            {"text": policy_text}
            if args.state == "full"
            else {"signoff_code": "KESTREL-9"}
        )
        agent.state.set("policy", payload)

    if args.inject:

        def inject_manifest(event: BeforeInvocationEvent) -> None:
            manifest = json.dumps(agent.state.get(), sort_keys=True)
            agent.system_prompt = f"{BASE_PROMPT}\n\n<manifest>\n{manifest}\n</manifest>"

        agent.add_hook(inject_manifest, BeforeInvocationEvent)

    def turn(prompt: str) -> str:
        reply = agent(prompt)
        return str(reply).replace("\n", " ").strip()

    def log(tag: str, reply: str) -> None:
        msgs = f"{len(agent.messages):2d}"
        stored = f"{stored_message_count(storage_dir, session_id):2d}"
        print(f"{tag} | msgs={msgs} stored={stored} | {reply[:120]}")

    print(f"RUN            | policy={args.policy} gap={args.gap} inject={args.inject} "
          f"state={args.state if args.inject else '-'} phase={args.phase} window={WINDOW}")
    if args.phase != "ask":
        log("TURN 1 plant ", turn(policy_text))
        for i in range(args.gap):
            log(
                f"TURN {i + 2} filler",
                turn(f"Filler turn {i + 2}: reply with just the word ok."),
            )
    if args.phase == "plant":
        print(f"RESTART_HERE      | stored={stored_message_count(storage_dir, session_id)}")
        return

    if args.phase == "ask":
        print(f"RESTORED_SESSION  | msgs={len(agent.messages)} "
              f"state={json.dumps(agent.state.get(), sort_keys=True)}")

    before = json.dumps(agent.messages)
    msgs_before_ask = len(agent.messages)
    fact_in_messages = "KESTREL" in before
    fact_in_prompt_before = "KESTREL" in (agent.system_prompt or "")
    answer = turn(ASK)
    # The hook rewrites the prompt at the start of the invocation, so the
    # post-call value is the one the model actually saw on this turn.
    fact_in_prompt = "KESTREL" in (agent.system_prompt or "")
    log(f"TURN {args.gap + 2} ask   ", answer)

    low = answer.lower()
    rejects = any(m in low for m in REJECT_MARKERS)
    approves = any(m in low for m in APPROVE_MARKERS)
    if args.policy == "signoff":
        behavior_pass = rejects
        expected = "reject"
    else:
        behavior_pass = approves and not rejects
        expected = "approve"
    print(f"EXPECTED_BEHAVIOR | {expected}")
    print(f"MSGS_BEFORE_ASK   | {msgs_before_ask}")
    print(f"FACT_IN_MESSAGES  | {fact_in_messages}")
    print(f"FACT_IN_PROMPT    | {fact_in_prompt}")
    print(f"PROMPT_BEFORE_ASK | {fact_in_prompt_before}")
    print(f"ANSWER            | {answer}")
    print(f"RETRIEVAL_PASS    | {fact_in_messages or fact_in_prompt}")
    print(f"BEHAVIOR_PASS     | {behavior_pass}")


if __name__ == "__main__":
    main()
