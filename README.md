# Streaming Materialize Updates to the Browser

For today's Skunkworks project, I'm going to be showing how to continuously tail a materialized
view and stream the results directly to one or more users' browsers.

The rough dataflow will look like:

    source -> materialized <- tornado <- clients

## TODO

- [x] Spin up materialized and ingest wikipedia data
- [x] Write script to create interesting materialized views
- [x] Figure out how to tail messages from the console
- [x] Get tail working in vanilla Python
- [x] Spin up tornado to splat data onto the screen
- [x] What's a good dataset to show this off?
- [x] Come up with a few interesting materialized views.
- [x] Pipe output from `copy_expert` into a program that posts messages to tornado
- [ ] Write some javascript to receive these messages
- [ ] Perhaps visualize the results of the various views?

- [ ] Stretch Goal -- Stream Materialize internal tables to browser too
- [ ] Can we find two datasets that are good to show off joins?

## Not a Priority Anymore

- [ ] Figure out how to use tail with Momoko

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
