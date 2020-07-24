# Streaming Materialize Updates to the Browser

This project shows how to write a simple, end-to-end data processing pipeline that results in live
updating visualizations in the browser. It works as follows:

- Live updates to Wikipedia are streamed to a local file
- Materialized watches this file, ingesting events and updating views in real time
- A python process, per view, tails live updates from Materialize and `POST`s updates to a web
  server
- On each `POST` event, the web server broadcasts events to clients via websockets
- On receiving each event, the client will redraw to display the new information

The entire flow of data is event-triggered. At no point do we poll for data or run batch queries.
For a more detailed writeup, please see my [blog
post](https://materialize.io/streaming-tail-to-the-browser-a-one-day-project/).

## Running it locally

Right now, the startup sequence must be carefully orchestrated and will require 5 terminal
windows. The sequence of commands are:

### Terminal 1 - Tail Wikipedia Edits

```sh
./bin/stream_wikipedia
```

### Terminal 2 - Materialized

```sh
materialized -w 16
```

In another, temporary terminal, run:

```sh
./bin/create_views
```

### Terminal 3 - Tornado App Server

```sh
cd app && ./serve.py
```

### Terminal 4 - Tail Top10

```sh
./bin/stream_top10
```

### Terminal 5 - Tail Counts

```sh
./bin/stream_counts
```

### Open Browser!

Linux:

```sh
xdg-open http://localhost:8875
```

MacOS (I think it's open?)

```sh
open http://localhost:8875
```

## Skunksworks Day 2 Plan!

- [ ] Fix initial state bug
- [ ] Try psycopg3 to replace `tail | post` hacks
- [ ] Write one or two more views

## Fixing the Initial State Bug

`TAIL` gives a full stream of changes to the table that should be applied in order. There is
actually no need to run a base query. For the first improvement, the plan is to have the Tornado
server stored a compacted log of all updates from the `POST` handler.

Then, the server logic will be:

- On a new connection, write all messages in the buffer to the client.
- On a new message, broadcast the message to all listeners.

The client logic will simply be:

- Open websocket, get stream of updates, apply them in a compacted form

### Tradeoff

We're effectively storing a compacted view of the data in three places - Materialized, Tornado and
the Client. I think this is okay.

If we want to reduce the buffering in Tornado, then we have two options:

- Create a TAIL stream per client (maybe figure out how to join streams once two clients are in
  sync?). The dataset will never be buffered in Tornado. This has the potential downside of
  creating one Postgres connection per client
- Figure out how to query Materialize such the client can join the results of a `SELECT` with the
  `TAIL` stream. Unfortunately, it appears that `SELECT` does not return the `timestamps`
  necessary to write a correct update algorithm using `TAIL`.
