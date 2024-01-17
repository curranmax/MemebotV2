import argparse


class FeatureTracker:

    def __init__(self):
        self.parser = argparse.ArgumentParser()

        # Basic stuff
        self.parser.add_argument('-t', '--testing_mode', action='store_true')

        # Switches for individual features
        self.parser.add_argument('-ar', '--auto_reacts', action='store_true')
        self.parser.add_argument('-cc',
                                 '--chore_calendar',
                                 action='store_true')
        self.parser.add_argument('-es', '--emote_speller', action='store_true')
        self.parser.add_argument('-m', '--memes', action='store_true')
        self.parser.add_argument('-ot', '--ow_tracker', action='store_true')
        self.parser.add_argument('-oc', '--owl_calendar', action='store_true')
        self.parser.add_argument('-p', '--pugs', action='store_true')
        self.parser.add_argument('-tc',
                                 '--twitch_checker',
                                 action='store_true')

        # Switches for for feature groups
        self.parser.add_argument('-mb', '--meme_bot', action='store_true')
        self.parser.add_argument('-all', '--all_features', action='store_true')

        self.feature_groups = {
            'meme_bot': [
                'auto_reacts', 'emote_speller', 'memes', 'ow_tracker', 'pugs',
                'twitch_checker'
            ],
            'all_features': [
                'auto_reacts', 'chore_calendar', 'emote_speller', 'memes',
                'ow_tracker', 'owl_calendar', 'pugs', 'twitch_checker'
            ],
        }

        self.args = self.parser.parse_args()

    def isTestingMode(self):
        return self.args.testing_mode

    def isEnabled(self, feature):
        vs = vars(self.args)
        if feature not in vs:
            raise Exception('Unknown feature: ' + str(feature))

        if vs[feature]:
            return True

        for fg, fs in self.feature_groups.items():
            if feature in fs and fg in vs and vs[fg]:
                return True
        return False

    def printEnabledFeature(self):
        features = [
            'auto_reacts', 'chore_calendar', 'emote_speller', 'memes',
            'ow_tracker', 'owl_calendar', 'pugs', 'twitch_checker'
        ]
        enabled_features = [f for f in features if self.isEnabled(f)]
        disabled_features = [f for f in features if not self.isEnabled(f)]
        print('--------------------')
        print('| Enabled Features |')
        print('--------------------')
        for ef in enabled_features:
            print('    ' + ef)

        print('---------------------')
        print('| Disabled Features |')
        print('---------------------')
        for df in disabled_features:
            print('    ' + df)
