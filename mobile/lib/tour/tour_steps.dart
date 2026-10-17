import 'app_tour.dart';

const _helper = TourStop('helper', 'Mitra stays beside you',
    'Ask about this page by speaking or typing. Review proposed changes before saving them.');
const _prepared = TourStop('prepared', 'A little head start',
    'Open Saathi’s prepared suggestions. Check the details, edit the draft if needed, then choose whether to save it.');
const _replay = TourStop('replay', 'Come back anytime',
    'Use this compass to replay the current page’s tour. Skip and Done keep this guide dismissed on this phone.');
List<TourStop> tourSteps(String scope) {
  if (scope.startsWith('onboarding-')) {
    final stage = int.tryParse(scope.split('-').last) ?? 0;
    return [
      const TourStop('read', 'We can take this slowly',
          'Listen to Mitra’s guidance here. The microphones beside fields let you speak your answers; you can always type instead.'),
      ...switch (stage) {
        0 => [
            const TourStop('name', 'A little hello',
                'Tell Mitra your name. Use the microphone in this field or type it yourself.')
          ],
        1 => [
            const TourStop('location', 'Your corner of the world',
                'Choose to use your phone’s location for nearby weather. Permission is requested only when you tap it; you can enter your place instead.')
          ],
        2 => [
            const TourStop('crops', 'What do you grow?',
                'Add your crops here. Check spoken words before continuing.'),
            const TourStop('area', 'Your land, in hectares',
                'This app field uses hectares. Review the number and units, and only use the phone’s position for a field if you are there.')
          ],
        _ => [
            const TourStop('routines', 'Review your starter routines',
                'Read the routines and choose whether to add their drafts to your notebook. They do not mark farm work as completed.')
          ],
      },
      TourStop(
          'continue',
          stage == 3 ? 'Save when you are ready' : 'One small step at a time',
          stage == 3
              ? 'Check your profile and farm details before saving. The tour never saves or approves them.'
              : 'Continue when you are ready. Unfinished setup is kept on this phone so you can return later.'),
      const TourStop('skip', 'Explore first if you prefer',
          'Skip setup for now and return from your profile. Skipping this guide does not submit your details.'),
      _replay,
    ];
  }
  if (scope.startsWith('notebook-')) {
    final tab = scope.substring(9);
    final description = switch (tab) {
      'fields' =>
        'Add farms, fields and growing seasons. Review location and units before saving.',
      'ledger' =>
        'Record income and costs. Keep actual amounts separate from estimates and check the date.',
      'followups' =>
        'Keep crop observations and follow-ups together as conditions change.',
      'missions' =>
        'Review starter routines and make plans your own. A plan is not automatically a scheduled task.',
      'records' => 'Find saved memories, files and other farm records here.',
      _ => 'See your saved farm summary and work that needs attention today.',
    };
    return [
      TourStop('tabs', 'Your farm notebook', description),
      if (['fields', 'ledger', 'followups', 'missions'].contains(tab))
        TourStop('$tab-add', 'Add a farm record',
            'Open an editor here. Type or speak the details, then check and save them.'),
      if (tab == 'fields')
        const TourStop('add-field', 'Keep each field separate',
            'Add a field under a farm. Check hectares, soil and location before saving.'),
      _helper,
      _replay
    ];
  }
  return switch (scope) {
    'home' => const [
        TourStop('voice', 'Your voice comes first',
            'Talk to Mitra opens a dedicated voice call screen. You control recording and can read captions as you speak.'),
        TourStop('chat', 'Prefer to type?',
            'Open chat for questions, files and plans. Your conversations stay available in history.'),
        TourStop('profile', 'Make yourself at home',
            'Your profile, language and preferences live here. Keep your farm details up to date.'),
        TourStop('tools', 'Everything for your farm',
            'Open weather, tasks, Crop Doctor, markets, notebook, station, exchange and support. Each screen has its own short guide.'),
        _replay
      ],
    'chat' => const [
        TourStop('message', 'Say it in your own words',
            'Type your question or describe a task. You can keep a draft while Mitra works.'),
        TourStop('dictate', 'Speak a message',
            'Use this microphone for a spoken message. Review the transcript before sending.'),
        TourStop('attachment', 'Show Mitra what you mean',
            'Add a crop photo, report or document. Check the selected file before sending.'),
        TourStop('history', 'Pick up where you left off',
            'Previous conversations live here. Open one to continue it.'),
        TourStop('new-chat', 'A fresh conversation',
            'Start a new chat here. Your previous chats remain in history.'),
        _replay
      ],
    'calendar' => const [
        TourStop('add-task', 'Make room for your next task',
            'Ask Mitra to prepare a task for your selected date. Review the details before saving.'),
        TourStop('calendar-view', 'Find the right day',
            'Switch between month and agenda views, then choose a date to see its tasks.'),
        TourStop('deleted', 'Review removed tasks',
            'Find removed tasks here. Existing tasks also offer completion and editing controls.'),
        _helper,
        _replay
      ],
    'weather' => const [
        TourStop('nearby', 'Weather near you',
            'Tap to request your phone’s location for a regional forecast. This guide does not request permission.'),
        TourStop('city', 'Look at another place',
            'Search a city here. Check which location and forecast time you are viewing before planning field work.'),
        _helper,
        _replay
      ],
    'crops' => const [
        TourStop('photo', 'Start with a clear photo',
            'Choose a photo of the affected crop. A clear, well-lit image helps the crop check.'),
        TourStop('diagnose', 'Take a closer look',
            'Run the crop check after adding a photo. Review the result and follow-ups; serious or uncertain problems need a local expert.'),
        _prepared,
        _helper,
        _replay
      ],
    'markets' => const [
        TourStop('market-search', 'Find your crop and mandi',
            'Open search to change the crop or state. Your saved crops can also appear as quick choices.'),
        TourStop('comparison', 'Compare what you take home',
            'Include transport and market fees, and compare matching grades and units. Dated market prices are estimates, not guaranteed offers.'),
        _helper,
        _replay
      ],
    'schemes' => const [
        TourStop('scheme-search', 'Find support that fits',
            'Search for the kind of support you need. Review eligibility and use the official source before applying.'),
        _prepared,
        _helper,
        _replay
      ],
    'exchange' => const [
        TourStop('exchange-new', 'Share an offer or a need',
            'Prepare a listing for equipment, a resource or help. Review it before publishing.'),
        TourStop('exchange-mitra', 'Prepare it with Mitra',
            'Describe what you can offer or what you need. Mitra can help turn your words into a draft.'),
        TourStop('exchange-tabs', 'Keep the conversation together',
            'Browse resources, manage your listings and open exchange chats here. Discuss terms before agreeing to a handover.'),
        _replay
      ],
    'profile' => const [
        TourStop('edit-profile', 'Your farm, kept up to date',
            'Edit your saved details here. The same account uses these details on your phone and laptop.'),
        TourStop('profile-fields', 'Your farms and fields',
            'Open the notebook to review your land, seasons and field locations.'),
        TourStop('language', 'Your preferred language',
            'Choose the language you feel most at home with. Theme and sign-out controls are below.'),
        _replay
      ],
    'station' => const [
        TourStop('station', 'A pulse on your field',
            'This page shows available station readings and connection details. A missing measurement needs a connected source; it is never made up.'),
        _helper,
        _replay
      ],
    'saathi' => const [
        TourStop('checkins', 'Choose your check-ins',
            'Enable or pause Saathi’s background follow-ups here. This tour does not change the setting.'),
        TourStop('frequency', 'At your pace',
            'Choose how often you want check-ins. Review activity and connected channels below.'),
        _replay
      ],
    _ => const [_replay],
  };
}
