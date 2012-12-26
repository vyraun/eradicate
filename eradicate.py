"""Removes commented-out Python code."""

from __future__ import print_function

from io import StringIO
import os
import re
import tokenize

__version__ = '0.1'


def comment_contains_code(line):
    """Return True comment contains code."""
    line = line.lstrip()
    if not line.startswith('#'):
        return False

    line = line.lstrip(' \t\v\n#').strip()

    # Check that this is possibly code.
    for symbol in list('()[]{}:=') + ['print', 'return', 'break', 'continue',
                                      'import']:
        if symbol in line:
            break
    else:
        return False

    # Handle multi-line cases manually.
    for ending in ')]}':
        if line.endswith(ending + ':'):
            return True

    for symbol in ['else', 'try', 'finally']:
        if re.match(r'^\s*' + symbol + r'\s*:\s*$', line):
            return True

    for remove_beginning in ['print', 'return']:
        line = re.sub('^' + remove_beginning + r'\b\s*', '', line)

    try:
        compile(line, '<string>', 'exec')
        return True
    except (SyntaxError, TypeError, UnicodeDecodeError):
        return False


def commented_out_code_line_numbers(source):
    """Yield line numbers of commented-out code."""
    sio = StringIO(source)
    try:
        for token in tokenize.generate_tokens(sio.readline):
            token_type = token[0]
            start_row = token[2][0]
            line = token[4]

            if (token_type == tokenize.COMMENT and
                    line.lstrip().startswith('#') and
                    comment_contains_code(line)):
                yield start_row
    except (tokenize.TokenError, IndentationError):
        pass


def filter_commented_out_code(source):
    """Yield code with commented out code removed."""
    marked_lines = list(commented_out_code_line_numbers(source))
    sio = StringIO(source)
    for line_number, line in enumerate(sio.readlines(), start=1):
        if line_number not in marked_lines:
            yield line


def fix_file(filename, args, standard_out):
    """Run filter_commented_out_code() on file."""
    encoding = detect_encoding(filename)
    with open_with_encoding(filename, encoding=encoding) as input_file:
        source = input_file.read()

    filtered_source = ''.join(filter_commented_out_code(source))

    if source != filtered_source:
        if args.in_place:
            with open_with_encoding(filename, mode='w',
                                    encoding=encoding) as output_file:
                output_file.write(filtered_source)
        else:
            import difflib
            diff = difflib.unified_diff(
                StringIO(source).readlines(),
                StringIO(filtered_source).readlines(),
                'before/' + filename,
                'after/' + filename)
            standard_out.write(''.join(diff))


def open_with_encoding(filename, encoding, mode='r'):
    """Return opened file with a specific encoding."""
    import io
    return io.open(filename, mode=mode, encoding=encoding,
                   newline='')  # Preserve line endings


def detect_encoding(filename):
    """Return file encoding."""
    try:
        with open(filename, 'rb') as input_file:
            from lib2to3.pgen2 import tokenize as lib2to3_tokenize
            encoding = lib2to3_tokenize.detect_encoding(input_file.readline)[0]

            # Check for correctness of encoding.
            with open_with_encoding(filename, encoding) as input_file:
                input_file.read()

        return encoding
    except (SyntaxError, LookupError, UnicodeDecodeError):
        return 'latin-1'


def main(argv, standard_out, standard_error):
    """Main entry point."""
    import argparse
    parser = argparse.ArgumentParser(description=__doc__, prog='eradicate')
    parser.add_argument('-i', '--in-place', action='store_true',
                        help='make changes to files instead of printing diffs')
    parser.add_argument('-r', '--recursive', action='store_true',
                        help='drill down directories recursively')
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument('files', nargs='+', help='files to format')

    args = parser.parse_args(argv[1:])

    filenames = list(set(args.files))
    while filenames:
        name = filenames.pop(0)
        if args.recursive and os.path.isdir(name):
            for root, directories, children in os.walk(name):
                filenames += [os.path.join(root, f) for f in children
                              if f.endswith('.py') and
                              not f.startswith('.')]
                for d in directories:
                    if d.startswith('.'):
                        directories.remove(d)
        else:
            try:
                fix_file(name, args=args, standard_out=standard_out)
            except IOError as exception:
                print(exception, file=standard_error)
