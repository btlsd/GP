# GP

gunpo project. text SF rpg

## Web Demo

`index.html` contains a simple Pyodide-based text RPG. Open it in a browser or run a local server (`python -m http.server`) and navigate to the file to play.

Clicking **게임 시작** plays a short opening sequence before the game begins. The output window shows the title "군포 프로젝트", and any initialization or runtime errors appear with their codes. The opening text is loaded from `opening.json` and typed to the screen with a typewriter effect; proper nouns such as "군포" are highlighted.

