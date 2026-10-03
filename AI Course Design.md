# AI Course Generation 

## Objective: 
Generate Course for Learners using generative AI

## Overview
The user provides neccessary specification and preferences and submit request to generate course. The request is queued and processed. The user wait for the response. The user can review and provide instructions to  refine during two phases: Course Outline Generation and Lesson Generation. After Completion, the user can save and publish the course.

For isolation, The Generate Course is linked to tenant id. Only the tenant is able to access it .

First, The user input is validated and prompt is created from prompt template. Necessary guard rail is present in the  prompt template.

Request Limit and Timeout: Set limits per tenant and per course or per user and a proper timeout  of long wait time .



# Privacy
- Verify the tenant ID and user permissions on every request and published course.
- Store each item with its tenant ID.
- Send the llm only the learner information and source the llm needed for the current outline or lesson.
- Encrypt stored data and connections, keep sensitive content out of logs, restrict access to uploaded materials, and set retention and deletion rules.
# Personalization
(tennant admin guide)
- Collect each learner’s goals, prior knowledge, preferred examples, and available study time, with their consent.
Use this profile to adjust lesson depth, examples, practice difficulty, and pacing while keeping the approved learning objectives consistent.
# Guardrails
- Treat user instructions and reference materials as untrusted input.

- Allow the AI to return clear failure outcomes, such as “insufficient information,” “not enough reliable sources,” or “unable to generate.”

- Require citations for source-based claims and check that citations point to the supplied materials.

- Validate AI output before presenting it for review. Flag unsupported or uncertain content instead of presenting it as fact.

- And other Guardrils to account for ...


## Workflow 
STEP 1: Gathering Course Specification and user prefrences form user
- Tenant Admin provides various course specifications and prefrences by filling up a strucured form.
- User Inputs
   - Course Name
   - Description
   - Expected No of Chapters
   - Difficulty (Begginer/Intermediate/Advanced/Expert)
   - Available Hour Per Week
   - Course Duration
   - Course References / Research Materials
   - Preferences and Instruction (personalization)

STEP 2: Validate User Input
- Validate Input Schema 
- Place a input in the XML notation (delimiters)- letting the llm know that the imput is untrusted.
- Validate Input content  using llama guard to prevent unsafe texts
- IF flagged items is found  then throw an exception.

## PHASE 1: Coures Outline Generation
STEP 3: Create Prompt from Template and Generate Course Outline by generating using LLM


Step 4: Analyze the Generate Outline using LLM for validation and consistency. 
- Review against the user provided specification 
- And validation like structure, citations, chapter counts, and time totals.
Step 5: Refine the outline if required , else go to next step

Step 6: User Review and Approves or refine by providing instruction


## PHASE 2: Course Content Generation


Step 7: Generate Course Content and Assignments
- For each lesson, generate content and assignments. provide only necessary context and instruction.
- Generate Each Lesson independently  in small batches , Provide sumarized context from previous lessons to prevent overlap and gaps.

Step 8: Analyze the generated content using LLM and ask for refinment if necessary
- check if astimate fit the weekly and total time budget 

Step 9: User Review and Refinement loop
- Run a final course-wide check before publishment 








