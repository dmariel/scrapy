import csv
import logging
import re
from io import StringIO

from scrapy.http import TextResponse, Response
from scrapy.selector import Selector
from scrapy.utils.python import re_rsearch, to_unicode


logger = logging.getLogger(__name__)


def xmliter(obj, nodename):
    """Return a iterator of Selector's over all nodes of a XML document,
       given the name of the node to iterate. Useful for parsing XML feeds.

    obj can be:
    - a Response object
    - a unicode string
    - a string encoded as utf-8
    """
    nodename_patt = re.escape(nodename)

    DOCUMENT_HEADER_RE = re.compile(r'<\?xml[^>]+>\s*', re.S)
    HEADER_END_RE = re.compile(fr'<\s*/{nodename_patt}\s*>', re.S)
    END_TAG_RE = re.compile(r'<\s*/([^\s>]+)\s*>', re.S)
    NAMESPACE_RE = re.compile(r'((xmlns[:A-Za-z]*)=[^>\s]+)', re.S)
    text = _body_or_str(obj)

    document_header = re.search(DOCUMENT_HEADER_RE, text)
    document_header = document_header.group().strip() if document_header else ''
    header_end_idx = re_rsearch(HEADER_END_RE, text)
    header_end = text[header_end_idx[1]:].strip() if header_end_idx else ''
    namespaces = {}
    if header_end:
        for tagname in reversed(re.findall(END_TAG_RE, header_end)):
            tag = re.search(fr'<\s*{tagname}.*?xmlns[:=][^>]*>', text[:header_end_idx[1]], re.S)
            if tag:
                namespaces.update(reversed(x) for x in re.findall(NAMESPACE_RE, tag.group()))

    r = re.compile(fr'<{nodename_patt}[\s>].*?</{nodename_patt}>', re.DOTALL)
    for match in r.finditer(text):
        nodetext = (
            document_header
            + match.group().replace(
                nodename,
                f'{nodename} {" ".join(namespaces.values())}',
                1
            )
            + header_end
        )
        yield Selector(text=nodetext, type='xml')

class TagReplacer():
    def __init__(self, default_encoding='utf-8'):
        self.default_encoding = default_encoding

    def replace(self, obj, old_tag, new_tag):
        """Replace all occurrences of old_tag to new_tag

        Args:
            obj (str|bytes|Response): The object that has the xml/html that should be changed
            old_tag (str): a valid tag name to replace
            new_tag (str): the new tag replacement

        Raises:
            TypeError:  if the passed obj is not of a valid type
            ValueError: is the passed tag names are not valid

        Returns:
            [str|bytes|Response]: return the new replaced object
        """
        if not self._validate_tag_name(old_tag):
            raise ValueError("invalid old_tag")
        if not self._validate_tag_name(new_tag):
            raise ValueError("invalid new_tag")

        decoded_text = self._decode(obj)
        new_text = self._sub_tags(old_tag, new_tag, decoded_text)
        return self._encode_as(new_text, obj)

    def _sub_tags(self, old_tag, new_tag, text):
        old_tag_pattern = r'(?<!\\<\/)'+old_tag+'(?=((\s+\w+=".+")\s*)*>)'
        return re.sub(old_tag_pattern, new_tag, text, re.MULTILINE)

    def _validate_tag_name(self, tag):
        if not isinstance(tag, str):
            return False

        return re.match(r"^[a-z0-9-:_]{1,}$", tag) is not None
    
    def _decode(self, obj):
        decoded = None
        # Decode to string
        if isinstance(obj, Response):
            decoded = obj.text
        elif isinstance(obj, str):
            decoded = obj
        elif isinstance(obj, bytes):
            decoded = obj.decode(self.default_encoding)
        else:
            raise TypeError("Unsupported type")

        return decoded
    
    def _encode_as(self, newBody, oldObj):
        if isinstance(oldObj, Response):
            return oldObj.replace(body=newBody)
        elif isinstance(oldObj, str):
            return newBody
        elif isinstance(oldObj, bytes):
            return newBody.encode(self.default_encoding)
        else:
            raise TypeError("Unsupported type")



def xmliter_lxml(obj, nodename, namespace=None, prefix='x'):
    from lxml import etree
    nodename_sanitized = nodename
    obj_sanitized = obj
    if nodename.find(":") > 0:
        nodename_sanitized =  nodename.replace(":", "-")
        tag_replacer = TagReplacer()
        obj_sanitized =  tag_replacer.replace(obj, nodename, nodename_sanitized)
    reader = _StreamReader(obj_sanitized)
    tag = f'{{{namespace}}}{nodename_sanitized}' if namespace else nodename_sanitized
    iterable = etree.iterparse(reader, tag=tag, encoding=reader.encoding)
    selxpath = '//' + (f'{prefix}:{nodename_sanitized}' if namespace else nodename_sanitized)
    for _, node in iterable:
        nodetext = etree.tostring(node, encoding='unicode')
        node.clear()
        xs = Selector(text=nodetext, type='xml')
        if namespace:
            xs.register_namespace(prefix, namespace)
        yield xs.xpath(selxpath)[0]


class _StreamReader:

    def __init__(self, obj):
        self._ptr = 0
        if isinstance(obj, Response):
            self._text, self.encoding = obj.body, obj.encoding
        else:
            self._text, self.encoding = obj, 'utf-8'
        self._is_unicode = isinstance(self._text, str)

    def read(self, n=65535):
        self.read = self._read_unicode if self._is_unicode else self._read_string
        return self.read(n).lstrip()

    def _read_string(self, n=65535):
        s, e = self._ptr, self._ptr + n
        self._ptr = e
        return self._text[s:e]

    def _read_unicode(self, n=65535):
        s, e = self._ptr, self._ptr + n
        self._ptr = e
        return self._text[s:e].encode('utf-8')


def csviter(obj, delimiter=None, headers=None, encoding=None, quotechar=None):
    """ Returns an iterator of dictionaries from the given csv object

    obj can be:
    - a Response object
    - a unicode string
    - a string encoded as utf-8

    delimiter is the character used to separate fields on the given obj.

    headers is an iterable that when provided offers the keys
    for the returned dictionaries, if not the first row is used.

    quotechar is the character used to enclosure fields on the given obj.
    """

    encoding = obj.encoding if isinstance(obj, TextResponse) else encoding or 'utf-8'

    def row_to_unicode(row_):
        return [to_unicode(field, encoding) for field in row_]

    lines = StringIO(_body_or_str(obj, unicode=True))

    kwargs = {}
    if delimiter:
        kwargs["delimiter"] = delimiter
    if quotechar:
        kwargs["quotechar"] = quotechar
    csv_r = csv.reader(lines, **kwargs)

    if not headers:
        try:
            row = next(csv_r)
        except StopIteration:
            return
        headers = row_to_unicode(row)

    for row in csv_r:
        row = row_to_unicode(row)
        if len(row) != len(headers):
            logger.warning("ignoring row %(csvlnum)d (length: %(csvrow)d, "
                           "should be: %(csvheader)d)",
                           {'csvlnum': csv_r.line_num, 'csvrow': len(row),
                            'csvheader': len(headers)})
            continue
        else:
            yield dict(zip(headers, row))


def _body_or_str(obj, unicode=True):
    expected_types = (Response, str, bytes)
    if not isinstance(obj, expected_types):
        expected_types_str = " or ".join(t.__name__ for t in expected_types)
        raise TypeError(
            f"Object {obj!r} must be {expected_types_str}, not {type(obj).__name__}"
        )
    if isinstance(obj, Response):
        if not unicode:
            return obj.body
        elif isinstance(obj, TextResponse):
            return obj.text
        else:
            return obj.body.decode('utf-8')
    elif isinstance(obj, str):
        return obj if unicode else obj.encode('utf-8')
    else:
        return obj.decode('utf-8') if unicode else obj
