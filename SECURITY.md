# Security policy

## Supported versions

Only the current `main` receives security fixes. Please reproduce a problem on the latest commit before reporting it.

## Reporting a vulnerability

Report vulnerabilities **privately** through GitHub's private vulnerability reporting: open the repository's **Security** tab, choose **Advisories**, then **Report a vulnerability**. Please do not open a public issue or pull request for a security problem.

Include what you can: the commit you tested, how you run it (Docker image, local dev servers), reproduction steps or a proof of concept, and the impact you expect. If the problem needs a crafted `.xer`, attach a minimal synthetic one; **never send a real project's file**.

This is a spare-time project, so there is **no SLA**. I will try to acknowledge reports within a week and to publish a fix and advisory as soon as is practical; credit is given unless you prefer otherwise.

## How XERlock treats uploads

The promise in the name is part of the security model. An uploaded `.xer` is streamed to a temporary file (capped at 50 MB as bytes arrive), parsed, and the temporary file is deleted when the request ends, whether the parse succeeds or fails. Nothing is stored server-side: no database, no upload directory, no logs of file contents. A test asserts that no uploaded file survives the request.

The parsed schedule is kept **in the user's browser**, not on the server: the last opened file and review annotations in `localStorage`, saved snapshots in IndexedDB. Anyone with access to that browser profile can read them, so on a shared computer clear the site's data when you are done.

The app has **no authentication of its own**. It is meant to run on your own infrastructure; if you expose it beyond a trusted network, put it behind a reverse proxy that authenticates users.

## Scope

In scope: the FastAPI backend, the Vue frontend and the Docker image built from this repository. For example, a crafted `.xer` that executes script in the browser, reads files on the server, survives the request on disk, or exhausts the server despite the upload cap.

Out of scope: deployments exposed to the internet without the authentication layer recommended above, problems that need an already-malicious operator, and vulnerabilities in third-party software (such as MPXJ) that only affect XERlock through a version you did not get from this repository. Report those upstream.
