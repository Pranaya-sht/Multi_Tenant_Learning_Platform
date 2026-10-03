# How I used AI while building this project

I used Codex to help with coding, review, and testing. I usually asked about one part of the app at a time, such as a permission check, a tenant-scoped query, or a failing test. Stitch gave me a starting point for the frontend, but I adapted the design to the React app and connected it to the real API.

I kept the project rules in [`AGENTS.md`](../AGENTS.md), including the stack, file layout, commands, and tenant-isolation requirements. That saved me from repeating the same background in every request. I worked from the files relevant to the task instead of sending the whole repository, and kept follow-up requests focused on what the previous check found. I did not measure token savings, but this kept the context and responses shorter.

I checked the work with pytest against PostgreSQL and Redis, browser tests using isolated data, lint and formatting checks, the frontend build, and Alembic's migration check. An AI response alone was not my evidence that a feature worked. The AI course-generation design was kept separate and was not written by Codex.

The [selected coding instructions](../prompts.md) contain major excerpts from the AGENTS.md context supplied to the assistant, grouped for readability. A [tenant-boundary review skill](../skills/review-tenant-boundaries/SKILL.md), prepared with AI assistance after the implementation review, captures a focused review procedure for future changes.
