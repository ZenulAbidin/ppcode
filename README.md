ppcode
======

A BBCode to HTML converter in Python

ppcode.py is a small library currently containing a set of classes to process BBCode into HTML. To use instantiate a
ppcode.PPDecode object, pass a string to .decode and accept the HTML fragment as the return value.


test.bb and test2.bb were created to torture test the parsing, the main goal of the design of this system is to be
highly resistent to malformed code, and to recover gracefully, in the end to create as intutivie environment for
the user as possible, and to create as well-formed HTML as possible even in the face of unbalanced tags, etc.
