# AWS documentation excerpts checked for the UC06 guardrail reply

Checked 2026-11-12 GMT+8 by fetching the two official pages with curl and stripping HTML.

## 1. Model invocation logging

URL: https://docs.aws.amazon.com/bedrock/latest/userguide/model-invocation-logging.html

Verbatim excerpts from the page:

> Model invocation logging is disabled by default. After model invocation logging is enabled, logs are stored until the logging configuration is deleted.

> Before you can enable invocation logging, you need to set up an Amazon S3 or CloudWatch Logs destination.

> input.inputTokenCount The number of input tokens in the request.

> output.outputTokenCount The number of output tokens in the response.

> requestMetadata An optional JSON object of key-value tags supplied by the caller. Present only when the caller provides request metadata.

> NoteEvery field in the record is populated by Amazon Bedrock automatically, with one exception: requestMetadata is the only field supplied by the caller.

The page's example log record contains `schemaType`, `schemaVersion`, `timestamp`, `accountId`, `region`, `requestId`, `operation`, `modelId`, `identity.arn`, `requestMetadata`, `input.inputTokenCount`: 25 and `output.outputTokenCount`: 150.

## 2. CloudWatch runtime metrics

URL: https://docs.aws.amazon.com/bedrock/latest/userguide/monitoring-runtime-metrics.html

Verbatim excerpts from the page:

> The Amazon Bedrock bedrock-runtime.region.amazonaws.com endpoint publishes metrics to Amazon CloudWatch under the AWS/Bedrock namespace. Use these metrics to monitor invocation volume, latency, token consumption, error rates, and model invocation logging delivery.

> InputTokenCount Count Number of tokens in the input.

> OutputTokenCount Count Number of tokens in the output.

> NoteAmazon Bedrock publishes the preceding metrics both with and without the ModelId dimension. If a request fails before Amazon Bedrock determines which model the request targets, the metrics for that request are published without the ModelId dimension. As a result, filtering by ModelId can undercount errors. To account for all requests, query these metrics without specifying a dimension.

These are CloudWatch metrics (aggregated series), not per-invocation JSON records. The per-invocation detail is in the model invocation log described above.

## Scope of this file

This is documentation, not an experiment. The UC06 bench did not enable Bedrock model invocation logging, did not query CloudWatch, and did not attach per-request metadata. Any recommendation to reconcile against these sources is a design recommendation, not a measured result.
