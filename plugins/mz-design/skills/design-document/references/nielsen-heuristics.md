# Nielsen's 10 Usability Heuristics — Reference

Grep-first reference file. UX critics consult this file for the specific heuristic they are applying; do not load the whole file.

Source: Nielsen Norman Group, "10 Usability Heuristics for User Interface Design", 1994, reviewed 2020. https://www.nngroup.com/articles/ten-usability-heuristics/

## 1. Visibility of system status

**Principle**: The design should always keep users informed about what is going on, through appropriate feedback within a reasonable amount of time.

**Probing questions**:

- Does every user action produce visible feedback within ~1 second?
- Are loading, saving, processing, and error states clearly distinguished?
- Is the user's current location in the navigation always visible?
- Are pending items distinguished from completed ones?

**Common violations**: silent failures on submit; no loading spinner during async work; missing "saved" confirmation; active nav item not highlighted.

## 2. Match between system and the real world

**Principle**: The design should speak the users' language, using words, phrases, and concepts familiar to the user. Follow real-world conventions, making information appear in a natural and logical order.

**Probing questions**:

- Does the copy use domain language the target user understands?
- Are metaphors drawn from real-world analogues (trash, folder, draft)?
- Is iconography conventional for the domain, or is it inventing new visual language without need?
- Does information order match the user's mental model of the task?

**Common violations**: developer jargon in user-facing copy; abstract icons without labels; alphabetical ordering when frequency ordering would be more useful.

## 3. User control and freedom

**Principle**: Users often perform actions by mistake. They need a clearly marked "emergency exit" to leave the unwanted action without having to go through an extended process.

**Probing questions**:

- Can the user undo and redo the last action?
- Is there a cancel option in every multi-step flow?
- Can the user close a modal without completing it?
- Is navigation history preserved on back/forward?

**Common violations**: no undo; destructive actions without confirm; modals that trap the user; forms that lose data on back navigation.

## 4. Consistency and standards

**Principle**: Users should not have to wonder whether different words, situations, or actions mean the same thing. Follow platform and industry conventions.

**Probing questions**:

- Are interactive patterns (buttons, links, toggles) consistent across the product?
- Does the design follow the platform's HIG (iOS HIG, Material, Fluent) where applicable?
- Are the same actions labeled the same way in different contexts?
- Is visual styling consistent across similar components?

**Common violations**: "Save" vs "Submit" vs "Confirm" for the same action; mixed modal styles; inconsistent button sizes.

## 5. Error prevention

**Principle**: Good error messages are important, but the best designs carefully prevent problems from occurring in the first place. Eliminate error-prone conditions or check for them and present users with a confirmation option.

**Probing questions**:

- Are destructive actions gated by confirmation or undo?
- Are invalid inputs prevented at the UI level rather than caught post-submit?
- Are date pickers, selectors, and guided flows used instead of free-form text where possible?
- Does the design surface constraints before the user makes the mistake?

**Common violations**: free-text date fields; no confirm on delete; submit button enabled when required fields are empty.

## 6. Recognition rather than recall

**Principle**: Minimize the user's memory load by making elements, actions, and options visible. The user should not have to remember information from one part of the interface to another.

**Probing questions**:

- Are options visible rather than memorized (menus vs commands)?
- Are contextual hints, placeholders, and help text surfaced where needed?
- Does autocomplete reduce the need to remember exact values?
- Are breadcrumbs or location indicators present in deep hierarchies?

**Common violations**: command-line-like interactions; empty placeholders with no hint text; hidden settings behind memorized keyboard shortcuts.

## 7. Flexibility and efficiency of use

**Principle**: Shortcuts — hidden from novice users — may speed up the interaction for the expert user so that the design can cater to both inexperienced and experienced users.

**Probing questions**:

- Are keyboard shortcuts provided for frequent actions?
- Can power users configure defaults, templates, or saved views?
- Are bulk actions available for repeat operations?
- Does the design support both discovery and speed?

**Common violations**: no keyboard shortcuts; no multi-select; every task requires the same number of clicks whether novice or expert.

## 8. Aesthetic and minimalist design

**Principle**: Interfaces should not contain information that is irrelevant or rarely needed. Every extra unit of information in an interface competes with the relevant units and diminishes their relative visibility.

**Probing questions**:

- Is every element on screen pulling weight, or is there decorative noise?
- Are secondary and tertiary actions de-emphasized from primary ones?
- Is whitespace used to group related content and separate unrelated content?
- Does the color palette serve meaning (hierarchy, state) rather than decoration?

**Common violations**: too many primary buttons in one view; overuse of dividers; icon + label + badge + tooltip for a single item.

## 9. Help users recognize, diagnose, and recover from errors

**Principle**: Error messages should be expressed in plain language (no error codes), precisely indicate the problem, and constructively suggest a solution.

**Probing questions**:

- Does every error message tell the user what went wrong **and** how to fix it?
- Is the problematic field visually highlighted at the point of error?
- Is the error recoverable, or does the user have to start over?
- Does the tone avoid blame ("you failed") in favor of guidance ("this date must be in the future")?

**Common violations**: "Error 500"; validation message at the top of the form only; "Invalid input"; clearing the form after an error.

## 10. Help and documentation

**Principle**: It's best if the system doesn't need any additional explanation. However, it may be necessary to provide documentation to help users understand how to complete their tasks.

**Probing questions**:

- Is there contextual help (tooltips, empty states, inline hints) at the point of need?
- Is the help searchable and task-oriented rather than feature-oriented?
- Are first-time experiences designed to teach progressively?
- Is there a way to re-trigger a tutorial or tour?

**Common violations**: help buried in a separate site; tour only runs on first login; no contextual tooltips; documentation organized by feature rather than task.
