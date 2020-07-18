# Streaming Materialize Updates to the Browser

## Original Plan

For today's Skunkworks project, I'm going to be showing how to continuously tail a materialized
view and stream the results directly to one or more users' browsers.

The rough dataflow will look like:

    source -> materialized <- tornado <- clients

## Where Did I End Up?

I was able to create an end-to-end, event driven streaming pipeline using Materialized views. The
end workflow ended up looking something more like this:

    source -> file <- materialized <- tail | post -> tornado <- clients

Basically, we have a source that is reading data from a remote source and writing the contents to
a file. That file is being tailed by materialize and using the results of that to update
materialized views. This is exactly as described in the demo docs.

The parts I had to figure out today were the following:

### Getting Started with Materialize
I've never actually used Materialized. Pleasantly this took very little time and worked as
expected.

### Tail | Post
Creating two scripts that could read the results of the tail and pipe that data into Tornado. I
ended up needing two scripts, as I could not find a fast way to implement a non-blocking method
for using `psycopg2 copy_expert` and ended up resortin to unix pipes. So, there is one script that
reads the result of the tail and outputs that to stdout. The second script reads from stdin,
parses the Materialize tail output, converts to JSON and POSTs the result of that to the Tornado
server.

### Tornado Server
This part was pretty straightforward. Create a non-blocking Tornado server that can query the
database using `momoko` as a non-blocking wrapper around `psycopg2`, accepts JSON blobs via a POST
request and broadcast those post requests.

### Javascript Client
Pretty simple little bit of code to open a websocket, read the results and update HTML in
response. The Top10 editors even get a nice little barchart that auto-updates in all sorts of
funny ways.

## Future Work

I'd love to cut out most of the middlemen and simply expose changelogs (`tail`) over websockets
from materialized. This would cut out most of the complexity. It would also enable a much simpler
"base + patches" stream of updates, as the client wouldn't need to figure out how to synchronize
the view and changelog.

## TODO

- [x] Spin up materialized and ingest wikipedia data
- [x] Write script to create interesting materialized views
- [x] Figure out how to tail messages from the console
- [x] Get tail working in vanilla Python
- [x] Spin up tornado to splat data onto the screen
- [x] What's a good dataset to show this off?
- [x] Come up with a few interesting materialized views.
- [x] Pipe output from `copy_expert` into a program that posts messages to tornado
- [x] Write some javascript to receive these messages
- [x] Write some javascript to update HTML on these messages!
- [x] Perhaps visualize the results of the various views?

- [ ] Implement a sane update mechanism for the visualization
- [ ] Stretch Goal -- Stream Materialize internal tables to browser too
- [ ] Can we find two datasets that are good to show off joins?

## Abandoned

- [ ] Figure out how to use tail with Momoko or Tornado

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
