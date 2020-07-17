# Streaming Materialize Updates to the Browser

For today's Skunkworks project, I'm going to be showing how to continuously tail a materialized
view and stream the results directly to one or more users' browsers.

The rough dataflow will look like:

    source -> materialized <- tornado <- clients

## TODO

- [ ] Spin up materialized and ingest data
- [ ] Spin up tornado plus a single javascript page to splat data onto the screen
- [ ] What's a good dataset to show this off?
- [ ] Come up with a few interesting materialized views.
- [ ] Can we find two datasets that are good to show off joins?
- [ ] Perhaps visualize the results of the various views?

## Web Server Logic

- Accept an incoming connection request, `GET /view/stream`
- Insert client socket onto list of listeners for `delta` messages
- Query current view to produce a `diff` message.

## Client Side Logic

The client will receive a stream of messages from the server. There will be two types of messages:

    base
    delta

A `base` message contains the results of the view at a given point in time, queried upon first
connection by an individual client. The `delta` message is an array of inserts and deletes that
should be applied continuously to base to keep the dataset in sync.

Clients should only ever see a single `base` message and should expect to see a never ending
stream of `delta` messages.

On initial load, the client may start seeing `delta` messages before it sees a `base` message.
This is to ensure that the client sees all messages required to keep the dataset in sync. Clients
should buffer, and optionally compact, all `delta` messages until the `base` message arrives.

`delta` messages are considered idempotent. It's possible that the result of applying a `delta`
message will result in no changes, as the `base` message query may already have the `delta`
message applied within the database.
