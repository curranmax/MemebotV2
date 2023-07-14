
import argparse

def createParser():
    parser = argparse.ArgumentParser()

    # Basic stuff
    parser.add_argument('-t', '--testing_mode', action='store_true')

    # TODO allow each feature to add its own args

    return parser
