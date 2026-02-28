# Vista AI Front‑end

This directory is reserved for the React front‑end of the Vista AI project.  A full
implementation should include components to capture audio and video from the
user’s device, open a WebSocket connection to the `/ws/live` endpoint exposed
by the FastAPI backend, and render the assistant’s responses (both audio and
text) to the user.

For the purposes of this prototype, the React app is left as a placeholder.  You
can bootstrap a new React project here (e.g. using `npm init vite@latest` or
`create-react-app`), install necessary dependencies (like `@react-aria/live-announcer` or
a WebSocket client), and implement UI flows corresponding to each skill.