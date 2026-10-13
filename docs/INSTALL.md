# Install

This is an outline. The operator's full install steps for a specific machine are private, because they describe the
network, host, and virtual machine layout. Those steps follow [SECURITY.md](SECURITY.md), and the rules for keeping
them private are there too.

## Outline

1. **Model server.** Run a local model server on the host. Use a model that fits the memory you have, with a context
   window large enough for the agent's minimum.
2. **Host.** Prepare a virtual machine or a container host with a container runtime. Keep it on a private network,
   with no inbound route from outside.
3. **Configuration.** Copy `.env.example` to `.env` and `hermes-data/.env.example` to `hermes-data/.env`. Fill in real
   values only in those untracked copies. Never commit them.
4. **Network.** Put the agent on a network that can reach only an egress proxy and the local model server. Allow only
   the destinations the agent needs. Enforce this in the host firewall, not only in container configuration.
5. **Services.** Start the agent, the proxy, and the log stack. Confirm each one is running before you test it.
6. **Verify.** Test that a disallowed destination fails, that the allowed chat path works, and that logs reach the log
   store.

7. **Evaluate the model.** Before changing hardware or swapping models, run the same three or four tasks on each
   candidate: sort a sample inbox, summarize a board, turn rough notes into a project list. Score each run on the
   right tool, valid arguments, and stopping at the right point. See
   [SECURITY.md](SECURITY.md#work-integrations-email-and-notes-boards).

## Where the details are

Configuration files for steps 2, 4, and 5 are kept privately, outside this repository, and follow
[SECURITY.md](SECURITY.md#buildout-and-configuration). Build your own from the outline above, using the
[OWASP Agentic AI controls](SECURITY.md#agentic-ai-controls) as your checklist.
