"""Extensions considered ordinary. Used only to spot *unknown* extensions."""

BENIGN_EXTENSIONS = frozenset(
    "." + e for e in """
    txt log md rtf doc docx docm dot dotx odt ott pdf xps epub mobi
    xls xlsx xlsm xlsb xlt xltx ods csv tsv ppt pptx pptm pps ppsx odp key pages numbers
    jpg jpeg jpe png gif bmp tif tiff webp heic heif raw cr2 cr3 nef arw dng orf rw2 svg ico psd ai eps indd xcf
    mp3 wav flac aac ogg oga m4a wma aiff aif opus mid midi
    mp4 m4v mov avi mkv wmv flv webm mpg mpeg 3gp mts m2ts vob
    zip rar 7z tar gz tgz bz2 xz zst cab iso img dmg
    exe dll sys msi msp msu bat cmd ps1 psm1 vbs js jse wsf com scr cpl ocx drv efi mui cat inf ini cfg conf config reg
    lnk url desktop
    html htm xhtml mht mhtml css scss less xml xsd xsl json yaml yml toml
    py pyc pyd pyw ipynb java class jar kt c h cpp hpp cc cs vb go rs rb php pl swift ts tsx jsx lua sql sh r m
    db sqlite sqlite3 mdb accdb dbf ldf mdf bak tmp temp old swp
    eml msg pst ost mbox vcf ics
    ttf otf woff woff2 fon fnt
    dat bin pak cache idx etl evtx chm hlp manifest pdb
    torrent nfo srt sub ass vtt
    gpx kml kmz dwg dxf stl obj fbx blend 3ds max skp
    """.split()
)

# Typical extensions of user documents: "<name>.<doc ext>.<unknown>" is a
# typical sign of a ransomware appending its own extension.
DOCUMENT_EXTENSIONS = frozenset(
    "." + e for e in """
    doc docx xls xlsx ppt pptx pdf txt rtf odt ods odp csv jpg jpeg png gif bmp tif tiff
    mp3 mp4 avi mov zip rar 7z psd sql mdb accdb db
    """.split()
)
