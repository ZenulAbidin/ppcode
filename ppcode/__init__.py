"""A bbcode subset to HTML converter.

This module exports one class, PPDecode. To use this class to convert bbcode into
HTML, instantiate it and call the .decode member, passing the bbcode.

This decoder supports a subset of commonly-used bbcode which is called ppcode in
various places. The primary difference between bbcode and ppcode is in image and
url tags; in bbcode a form which allows the link to be named or the image to be
alt texted exists such as:

[url=http://www.foo.com]link to foo.com[/url].

This form is not supported in ppcode currently, the simpler form:

[url]http://www.foo.com[/url]

is supported. This is an implementation limitation and will be addressed in future
versions.
"""
from decode import PPDecode
