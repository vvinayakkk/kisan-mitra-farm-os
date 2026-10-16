/// Page-specific prompts, kept identical to `frontend/src/components/assistant/suggestions.ts`
/// so web and mobile ask the assistant the same way.
const Map<String, List<(String, String)>> kSuggestions = {
  'assistant': [
    ('Plan my week', 'Help me create a weekly farm work plan. Ask for the details you need.'),
    ('Make a budget', 'Help me create an Excel farm budget from my actual costs.'),
    ('Check a crop', 'Help me check a crop for symptoms. Ask for a crop photo and any essential details.'),
    ('Compare prices', 'Help me compare dated mandi prices. Ask which crop and location.'),
  ],
  'weather': [
    ('Plan around rain', 'Check the dated weather forecast and help me plan outdoor farm work around rain and wind.'),
    ('Heat and crops', 'Check the weather outlook and tell me what heat or humidity means for my crops. Ask about crop stage if needed.'),
    ('Compare places', 'Help me compare the weather for my farm and another city. Ask which city if I have not said it.'),
    ("This week's outlook", 'Summarize the next seven days of weather using source-backed forecast data.'),
  ],
  'today': [
    ('What matters today', 'Read my saved farm tasks and tell me the next practical step.'),
    ('Weather window', 'Check the available dated forecast for my farm before suggesting field work.'),
    ('Plan my day', 'Help me plan today using my actual open farm tasks.'),
    ('A quick note', 'Help me record a field observation; ask what happened and when.'),
  ],
  'fields': [
    ('Read my soil report', 'Help me read my saved soil report. Ask which field and report, and explain dated values and missing information.'),
    ('Plan a crop season', 'Help me prepare a crop season plan for one of my fields. Ask which crop and sowing date.'),
    ('Field summary', 'Summarize the farm and field details I have saved, without inventing missing information.'),
    ('Water context', 'Help me understand what field and water details matter for irrigation planning.'),
  ],
  'ledger': [
    ('Record a cost', 'Help me record a farm expense. Ask amount, description and date and show it for review.'),
    ('Money summary', 'Summarize my recorded income and costs. Keep estimates and receivables separate.'),
    ('Export ledger', 'Prepare an Excel sheet from my farm ledger, with actual and estimated entries labelled.'),
    ('Plan a budget', 'Help me prepare a budget for my crop using my saved costs.'),
  ],
  'followups': [
    ('Add an observation', 'Help me record a dated observation for my crop follow-up.'),
    ('Review my cases', 'Read my open crop cases and help me decide what to inspect next.'),
    ('Prepare expert questions', 'Make questions for a local crop expert based on my saved observations.'),
    ('Photo guidance', 'Explain how to take a useful crop photo for symptom assessment.'),
  ],
  'missions': [
    ('A new farm plan', 'Help me create a farm mission with practical steps. Ask about my goal.'),
    ('Review progress', 'Read my farm plans and tell me which steps remain.'),
    ('Plan next steps', 'Help me organise the next steps for an existing farm plan. Ask which plan.'),
    ('Create a checklist', 'Create a downloadable checklist from my saved farm mission.'),
  ],
  'memory': [
    ('What do you remember', 'Show the saved facts you remember about my farm and their evidence.'),
    ('Correct a fact', 'Help me correct something remembered about my farm. Ask which fact and its current value.'),
    ('Forget a fact', 'Help me forget a saved farm fact. Ask which one and show it for review.'),
    ('Keep context current', 'Review my saved farm context and ask about details that may have changed.'),
  ],
  'crops': [
    ('Check symptoms', 'Help me understand crop symptoms. Ask for a clear crop photo and the crop name.'),
    ('Make a care plan', 'Help me build a crop inspection and care plan. Ask about the symptoms and crop before suggesting treatment.'),
    ('Prepare a report', 'Help me prepare a crop scouting report from a verified photo assessment and my observations.'),
    ('Ask an expert', 'Help me make a checklist of questions to ask my local agronomist about uncertain crop symptoms.'),
  ],
  'markets': [
    ('Compare markets', 'Help me compare dated prices for my crop. Ask which crop and state.'),
    ('Explain a trend', 'Look up a dated price trend for a single market and variety. Ask for the crop and location.'),
    ('Make a price sheet', 'Create an Excel sheet from actual dated market prices. Ask which crop and state.'),
    ('Plan a sale', 'Help me prepare a selling checklist. Ask which crop, quantity and market. Do not promise a sale price.'),
  ],
  'schemes': [
    ('Find support', 'Find relevant farming schemes. Ask my state and what support I need.'),
    ('Application checklist', 'Help me prepare a scheme application checklist. Ask which scheme and verify the official requirements.'),
    ('Check requirements', "Help me understand a scheme's eligibility. Ask which scheme and essential details; do not claim guaranteed approval."),
    ('Make a document', 'Create a Word checklist for a farming scheme application after confirming the scheme and requirements.'),
  ],
  'records': [
    ('Record a cost', 'Help me save a farm expense. Ask for the amount, description and date; show it for review first.'),
    ('Export expenses', 'Create an Excel sheet from my saved expenses with a total.'),
    ('Revise a file', 'Help me revise one of my saved files. Ask which file and what to change.'),
    ('Season summary', 'Prepare a Word summary from my saved tasks and expenses, identifying any missing information.'),
  ],
  'station': [
    ('Check my readings', 'Check my station readings and their freshness. What needs attention?'),
    ('Water planning', 'Use my measured station values to help plan watering. Ask for crop and soil context before suggesting anything.'),
    ('Recent changes', 'Review the last 24 hours of my station measurements and explain any notable changes. Do not invent missing data.'),
    ('Save field report', 'Create a Word field report from my measured station data, including freshness and missing readings.'),
  ],
  'calendar': [
    ('Plan this week', 'Help me organize my saved farm tasks for this week. Ask what needs priority.'),
    ('Move a task', 'Help me reschedule a saved farm task. Ask which task and the new date.'),
    ('Find open tasks', 'Read my saved tasks and tell me what still needs to be done.'),
    ('Make a checklist', 'Turn my saved work plan into a downloadable checklist.'),
  ],
};

/// `RunRequest.workspace_view` accepts only these; notebook sub-pages report
/// themselves as `records`.
const kRunViews = {'assistant', 'station', 'calendar', 'crops', 'markets', 'schemes', 'records', 'weather'};

String runView(String context) => kRunViews.contains(context) ? context : 'records';
