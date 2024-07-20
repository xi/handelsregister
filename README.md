Nach [§9 des Handelsgesetzbuchs](https://www.gesetze-im-internet.de/hgb/__9.html)
muss das Handelsregister online verfügbar sein. Diese Verpflichtung wird durch
die Webseite <https://www.handelsregister.de> umgesetzt. Leider ist die
Umsetzung dieser Webseite furchtbar.

-   Die Seite ist langsam
-   Die Seite verwendet ohne erkennbaren Grund Cookies
-   Daten sind nur über die Suchformulare auffindbar. Es gibt keine API und
    kein erkennbares URL Schema. Etwas wie
    `https://www.handelsregister.de/HRB/16686` wäre nett gewesen.
-   Auch Hilfetexte haben keine Eigenständigen URLs, sodass es unmöglich ist,
    auf sie zu verweisen.
-   Nach einigen Minuten bekommt man eine Fehlermeldung, dass die Session
    abgelaufen sei. Dann muss man von vorne anfangen.
-   Es ist nicht erlaubt, mehr als 60 Abfragen pro Stunde zu machen.

Kurz: Die Webseite ich nicht benutzbar.

Deshalb habe ich dieses Skript gebaut. Benutzung:

```
python handelsregister.py search 'atos'  # search by keyword
python handelsregister.py xml HRB 16686  # get structured data for a specific entry
```
