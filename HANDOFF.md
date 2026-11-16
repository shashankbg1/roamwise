# Handoff: day 1 (16 Nov 2026)

## Done
- Backend: FastAPI, four agents on LangGraph (researcher, planner, budget checker, critic),
  streaming API, SQLite storage. 42 tests pass; CI is green.
- Front end: trip form, live agent feed, itinerary view, refine-by-chat, saved trips.
- Checked in a browser against live weather and places data: planned a Lisbon trip and refined
  it ("make day 2 cheaper" took it from $248 to $222).
- Issues #1 to #11 closed on the project board; #12 to #17 are the roadmap.

## Not verified
- The Claude provider (Anthropic API and Bedrock) has never been run against a real model.
  Everything so far ran on the rule-based mock.
- The Dockerfile has never been built (Docker is not installed on this machine).
- `make dev` as a single command: the front end's file watcher stalled in the agent's shell, so
  the servers were started separately with ROAMWISE_NO_WATCH=1. It may work normally in your
  own terminal.
- The OpenStreetMap (Overpass) servers did not respond during the build, so restaurant data
  was never seen live. Wikipedia supplied all places.
- The page was only checked at desktop width.

## Known weak spots
- The mock planner leans heavily on churches for "history" because Wikipedia returns many.
- Refusal fallbacks for the Claude provider are not implemented.

## Next
1. Read the code (start with backend/app/agents/graph.py and nodes.py).
2. Add an Anthropic API key or set up Bedrock and run one real plan (#13).
3. Flight and hotel estimates (#12), then AWS deployment (#14 to #16).
