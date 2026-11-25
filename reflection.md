# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

- Briefly describe your initial UML design.
- What classes did you include, and what responsibilities did you assign to each?

My initial UML design focused on separating the main responsibilities of the PawPal+ system into different classes. I included classes for the Owner, Pet, Task, and Scheduler.

The Owner class was responsible for storing basic information about the pet owner and their preferences. The Pet class stored information about the pet, such as its name and type. The Task class represented individual pet care activities and included information such as the task name, duration, and priority. The Scheduler class was responsible for taking the pet care tasks and creating a daily plan based on the available time and task priorities.

I designed the classes this way so that each class had a specific responsibility instead of putting all of the program logic into one large class. The Scheduler was intended to be the main class that connected the information from the other classes and used it to create the daily plan.


**b. Design changes**

- Did your design change during implementation?
- If yes, describe at least one change and why you made it.

Yes, my design changed somewhat during implementation. As I started implementing the scheduling logic, I realized that some responsibilities were better handled by the Scheduler instead of the individual Task objects. For example, the Task class mainly needed to store information about a task, while the Scheduler needed to determine which tasks should be included in the daily plan.

This change made the design easier to understand because the Task class represented what a task is, while the Scheduler handled how tasks are organized into a plan. I also made changes as I connected the classes to the Streamlit interface because I needed the UI to interact with the classes in a straightforward way.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

My scheduler considers several factors, including task duration, task priority, and the amount of time available to the pet owner. The priority of a task helps determine which tasks should be scheduled first, while the duration helps determine whether a task can fit into the owner's available time.

I decided that priority should matter more than duration because some pet care tasks are more important than others. For example, a medication task may have a higher priority than an enrichment activity. However, available time is also an important constraint because the scheduler should not create a plan that requires more time than the owner has available.

The scheduler therefore tries to balance the importance of a task with whether there is enough time to complete it.

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

One tradeoff my scheduler makes is that it may leave a lower-priority task unscheduled when there is not enough time to complete every task.

For example, if an owner only has 30 minutes available but has several tasks that would take 45 minutes total, the scheduler has to choose which tasks to include. It prioritizes the more important tasks instead of trying to include everything.

This is reasonable for PawPal+ because the purpose of the application is to help a busy pet owner create a realistic plan. A shorter plan containing the most important tasks is more useful than a schedule that looks complete but cannot realistically be finished.

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

I used AI throughout the project as a development and learning tool. I used it to brainstorm ideas for the UML design, think through class responsibilities, understand Python concepts, debug errors, and improve the organization of my code.

AI was especially helpful when I was unsure how to approach a problem. Instead of only asking for complete code, I also asked questions about why certain approaches worked and how different classes should interact. Prompts that included the specific error message, the relevant code, and what I was trying to accomplish were the most helpful because they gave the AI enough context to provide a useful response.

I also used AI to help think through scheduling scenarios and potential edge cases that I should test.

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

There were times when I did not accept an AI suggestion immediately. When AI suggested a particular implementation or code change, I considered whether it actually matched the requirements of PawPal+ and whether I understood what the code was doing.

I evaluated suggestions by comparing them with the project requirements, testing the code myself, and checking whether the output matched what I expected. If a suggestion caused a new error or did not produce the expected scheduling behavior, I changed the approach rather than simply keeping the AI-generated solution.

This helped me understand that AI can be useful for development, but I still need to make the final decisions and verify that the code actually works.
---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

I tested important scheduling behaviors, including whether tasks were added correctly, whether task priorities affected scheduling, whether tasks fit within the available amount of time, and whether the scheduler could create a daily plan from a list of tasks.

These tests were important because the main purpose of PawPal+ is to generate a realistic daily care plan. If the scheduler ignored priorities or scheduled more tasks than the owner had time for, the application would not meet its main requirement.

I also tested different combinations of tasks and durations to make sure that the scheduler behaved consistently.

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

I am reasonably confident that the main scheduling logic works correctly because I tested the major behaviors and checked the resulting plans against the expected results. Testing individual pieces of the scheduling process also made it easier to identify problems before connecting everything to the Streamlit interface.

If I had more time, I would test additional edge cases. These would include:

An owner having zero available time
A task with a duration of zero
Two tasks having the same priority
More tasks than can fit into the available time
A task that is longer than the owner's entire available time
A list with no tasks
Tasks with different combinations of high, medium, and low priorities
Multiple tasks that have the same name or duration

Testing these situations would help make the scheduler more robust.

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

The part of the project I am most satisfied with is connecting the scheduling logic to the overall PawPal+ concept. I liked seeing how information about the owner, pet, and individual tasks could be combined to produce an actual daily plan.

I am also satisfied with the process of breaking the project into smaller components. Instead of trying to build the entire application at once, I worked through the design, classes, scheduling logic, testing, and UI separately. This made the project more manageable and helped me understand how the different parts of a software system work together.

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?
If I had another iteration, I would improve the scheduling system by making it more sophisticated. For example, I would allow users to specify preferred times for certain tasks, such as scheduling a morning walk in the morning rather than simply placing it wherever there is available time.

I would also improve conflict handling and recurring tasks. Some pet care activities need to happen at specific times or frequencies, so the scheduler could be redesigned to account for those requirements.

I would also improve the Streamlit interface by making it easier for users to edit tasks and clearly understand why a particular task was included or left out of the schedule.


**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?

One of the most important things I learned from this project is that system design should happen before implementation, but the design can also evolve as you learn more about the problem. Creating the UML diagram helped me think about the responsibilities of each class before writing code, but implementation showed me where some responsibilities needed to be adjusted.

I also learned that working with AI requires judgment. AI can help with brainstorming, debugging, and explaining programming concepts, but I cannot assume that every suggestion is correct. I need to understand the problem, test the suggested solution, and make sure it actually satisfies the project requirements.
---

# Project 4: Extending PawPal+ into an Applied AI System

## 6. System design for the AI extension

**What I added and why.** I extended PawPal+ with an AI assistant that uses Claude in a tool-use loop. The owner can describe tasks in plain language, ask care questions answered from a cited care guide, and ask for their day's plan. I kept the original `Scheduler` as the part that decides what fits in the day. The AI calls it through a tool instead of making up schedules itself, because the scheduler is deterministic and already covered by 47 tests.

**Reliability.** Guardrails sit at three points: before the model (emergencies, prompt injection, empty input), between the model and the schedule (every `add_task` call is checked against the same rules as the form), and after the model (dose mentions and uncited advice). Emergencies never reach the AI, because a fixed "call your vet / poison control" message is safer than a generated one.

## 7. How I used AI during development

I used **Claude Code in VS Code** as a coding partner for the whole extension. I gave it the Project 4 rubric and my Module 2 code, and asked it to improve the project to meet the rubric. It proposed the design, wrote the new modules, tests and docs, and ran the tests and evaluation after each change. My part was steering: deciding what the project needed, testing it myself, and pushing back when results didn't work for me.

The most useful prompts gave the AI something concrete to check against: the exact rubric text, or the exact error message I got (`401 Invalid bearer token`). Vague requests produced vague plans. A rubric line or an error message produced a specific fix.

**A suggestion I accepted: index the care guide by section, not by file.**
The AI suggested splitting each care document into its `##` sections and tagging each with the species it applies to. I accepted it because I could measure the effect. `eval/compare_retrieval.py` shows the section-level index is more accurate (9/9 vs 8/9; the whole-file index answered a cat brushing question with the dog guide) and sends Claude **77% less text** (52 vs 223 words per question). It also gives precise citations like `cat_care.md > Litter box care`.

**I also accepted:** keeping my original `Scheduler` in charge of building the plan, and having the AI call it as a tool rather than write schedules itself. The scheduler already had 47 passing tests, and AI-written schedules would be harder to trust and test.

**A suggestion I rejected or revised: placeholder output in the README.**
After the first version, the AI's plan was for me to run the live demo with an API key and paste the output into README sections marked `TODO`. When I tried, my terminal's credentials failed with a 401 error, and I didn't have a working key. I didn't want to submit a README with placeholders, or with made-up output, so I asked for a different approach. The result was **offline mode**: without a key, the assistant still runs the guardrails, the care-guide search and the scheduler, and says clearly that it is offline. All sample output in the README is now real. Anyone grading the project can run it without paying for an API key, and the app keeps working if the AI service is down.

**I also revised:**
- The first error handling showed a raw traceback when the key was rejected. I had it changed to a plain message that says which setting to fix.
- Testing the app myself showed that "How often should I feed my dog?" returned the toxic-foods section instead of the feeding schedule, because "feed" didn't match "Feeding". I had light stemming added to the retriever and the question added to the eval, so the bug can't come back unnoticed.
- The first version of the retrieval comparison script reached into the retriever's private internals. It was rewritten so the retriever accepts a list of chunks directly, which is cleaner and reuses the same search code.

## 8. Limitations and future improvements

- **Keyword guardrails can be bypassed.** "My pup snacked on a Hershey bar" doesn't match the emergency patterns. Next step: add a small AI classifier as a second safety check, and grow the eval set with harder phrasings.
- **Small, project-written knowledge base.** 18 sections across 5 documents, with no breeds, health conditions or species beyond dogs and cats. It is not veterinary advice.
- **The agent can only add tasks.** It can't edit, complete or remove them yet. I'd add those tools along with a confirmation step before anything is deleted.
- **No persistence.** Everything lives in the Streamlit session and is lost on reload.
- **Live AI output varies,** so the live eval checks outcomes (task saved at 08:00, high priority) rather than exact wording.

**What I learned.** AI was fastest at the parts with a clear target: writing code to a spec, writing tests, and turning a rubric into a checklist. I had to slow down at the boundaries between parts, such as API credentials, how the UI behaves after an error, and whether sample output was real. Running the code myself and reading the actual error messages caught problems that looked fine on paper. The biggest lesson is to keep the AI's job narrow and checkable: Claude interprets requests and answers questions, while plain Python code that I can test decides the schedule and enforces safety.
