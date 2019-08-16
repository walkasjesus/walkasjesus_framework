# Bible lib

## Features

The bible lib can be used query bible texts in a variety of languages.

* Get a list of supported bibles using scripture.api.bible
* Caching of bible.api responses to reduce web traffic
* Get a single or multiple bible verses given a book, chapter and verse.
* Dutch HSV bible support

## Usage

``` python
from bible_lib import BibleFactory
from bible_lib import BibleBooks

# For a list of supported bibles using the scripture.api.bible
supported_bibles = Bibles().list()

bible = BibleFactory().create(supported_bibles[0].id)
# or 
bible = BibleFactory().create('HSV')

text = bible.verse(BibleBooks.John, 3, 16)
```