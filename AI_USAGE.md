# AI Usage Note

## Tools used

**ChatGPT** was used during the project for:

- Translating the assessment brief into functional requirements and a prioritized workflow.
- Brainstorming a simple application architecture.
- Drafting the SQLite schema and sample-data generation approach.
- Generating and debugging Python / Streamlit code.
- Reviewing the UI flow and identifying missing operational controls.

## Examples of human judgement over AI suggestions

### 1. Simpler architecture instead of a more complex system

A more elaborate architecture could have used multiple backend services and external integrations. I chose **Streamlit + SQLite** because the assignment is for a small fulfillment operation, the assessment allows dummy data, and the warehouse team is described as less comfortable with technology. The simpler architecture lets me demonstrate the operational workflow clearly without adding infrastructure that does not solve the core problems.

### 2. Verification instead of a simulated barcode platform

A full warehouse system could integrate physical barcode scanners. For the take-home project, I kept the control but implemented it as **exact SKU verification** before an order can move from Picking to Packing. This demonstrates the business control without pretending that a real scanner integration exists.

## Human review

AI-generated code and ideas were reviewed, simplified, and adapted to the specific fulfillment workflow described in the assessment. The final priorities and workflow rules are deliberate product decisions rather than an attempt to implement every possible feature.
