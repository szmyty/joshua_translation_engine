import argparse
import sys
from flask import Flask
from flask.ext.restful import reqparse, Api, Resource
from decoder import Decoder
from languages import new_lang_from_long_english_name
from text import PreProcessor

DEFAULT_TCP_PORT = 56748

app = Flask(__name__)
api = Api(app)

http_parser = reqparse.RequestParser()
http_parser.add_argument('inputText', type=unicode, location='json')
http_parser.add_argument('inputLanguage', type=str, location='json')

decoders = {}


class TranslationEngine(Resource):
    """
    Handle http post requests for translations by preprocessing inputs, getting
    translations from the relevant Joshua decoder, postprocessing and returning
    the results.
    """
    def post(self, target_lang_code):
        args = http_parser.parse_args()

        source_lang = new_lang_from_long_english_name(args['inputLanguage'])
        target_lang = new_lang_from_long_english_name(target_lang_code)
        lang_pair = (source_lang.short_name, target_lang.short_name)

        input_text = PreProcessor(source_lang).prepare(args['inputText'])
        translation = decoders[lang_pair].translate(input_text)

        response = {'outputText': translation}
        return response, 201


def handle_cli_args(argv):
    """
    Process all the command-line args (e.g. from sys.argv).
    """
    program_name = argv.pop(0)
    remaining_args = argv
    cli_parser = argparse.ArgumentParser(
        prog=program_name,
        usage='%(prog)s [options]\n'
              'Specify at least one bundle and source and target languages '
              'for each bundle. The order of -s and -t correspond to the '
              'order of -b options\n',
        description='Start a translation engine server.'
    )
    cli_parser.add_argument(
        '-b',
        '--bundle-dir',
        nargs='+',
        help="path to directory generated by Joshua's run_bundler.py script",
    )
    cli_parser.add_argument(
        '-s',
        '--source-lang',
        nargs='+',
        default=[],
        help='the two-character language code of the input text.',
    )
    cli_parser.add_argument(
        '-t',
        '--target-lang',
        nargs='+',
        default=[],
        help='the two-character language code of the output text',
    )
    cli_parser.add_argument(
        '-p',
        '--port',
        nargs='*',
        default=[],
        type=int,
        help='the TCP port(s). Either specify just one port, and the rest of '
             'the bundles will start on automatically incremented port '
             'numbers, or specify one port number per bundle. Omitting this '
             'option defaults to setting the first port number to %i.'
             % DEFAULT_TCP_PORT,
    )

    # Sanity check: at least one Joshua bundle
    if not remaining_args:
        sys.stderr.write(
            'ERROR: at least one Joshua decoder bundle and its source and '
            'target languages should be specified.\n'
        )
        cli_parser.print_help()
        sys.exit(2)

    parsed_args = cli_parser.parse_args(remaining_args)

    # Sanity check: source and target languages specified for each Joshua
    # bundle
    num_bundles = len(parsed_args.bundle_dir)
    mismatched_num_of_ports = (
        len(parsed_args.source_lang) != num_bundles or
        len(parsed_args.target_lang) != num_bundles
    )
    if mismatched_num_of_ports:
        sys.stderr.write(
            'ERROR: For each bundle, source and target languages must be '
            'specified.\n'
        )
        cli_parser.print_help()
        sys.exit(2)

    # Sanity check: a TCP port is assigned for each Joshua decoder.
    num_bundles = len(parsed_args.bundle_dir)

    if parsed_args.port == []:
        parsed_args.port = [DEFAULT_TCP_PORT + i for i in range(num_bundles)]

    elif len(parsed_args.port) == 1 and 1 < num_bundles:
        initial_port = parsed_args.port[0]
        parsed_args.port = [initial_port + i for i in range(num_bundles)]

    elif len(parsed_args.port) != num_bundles:
        sys.stderr.write(
            'ERROR: TCP ports specified incorrectly.\n'
        )
        cli_parser.print_help()
        sys.exit(2)

    return parsed_args

api.add_resource(
    TranslationEngine,
    '/joshua/translate/<string:target_lang_code>'
)

if __name__ == '__main__':

    args = handle_cli_args(sys.argv)
    for idx, bundle_confs in enumerate(zip(args.bundle_dir, args.port)):
        bundle, port = bundle_confs
        decoder = Decoder(bundle, port)
        decoder.start_decoder_server()
        lang_pair = (args.source_lang[idx], args.target_lang[idx])
        decoders[lang_pair] = decoder

    app.run(debug=True, use_reloader=False)
    #app.run()
