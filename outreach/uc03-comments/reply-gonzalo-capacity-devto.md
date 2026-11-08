That is a very close analogy. The important distinction in your OCI example is between an allowance and available inventory: quota describes what the tenancy may consume, while host capacity determines whether the requested launch can actually be placed.

The server-side wait also fits the retry point. A client retry setting can govern subsequent attempts, but it cannot shorten the time the service spends before returning the first response.

Your last sentence is the general rule: name the resource a limit actually controls, then look one layer below it for the failure it cannot see. Thanks for adding such a concrete cloud example.
