# hamkorger - Korg M01 MIDI extractor

**hamkorger** (named after hamburger) is a a MIDI extraction tool for .sav files from the Korg M01 game-app-thingy for the Nintendo DS. It exports a MIDI file with all the notes of a selected song from a save file.

## Usage

hamkorger has no dependencies. Simply download `hamkorger.py` and run it with Python, then follow the prompts. It was written and tested in Python 3.13, but it theoretically should work in lower versions.

## Currently unsupported features

hamkorger is not complete, and while basic exports work, some features of Korg M01 are unsupported or incomplete. If you want to help improve hamkorger, do the github things idk.

- **Attack/Release**: I'm not even sure how this works in MIDI (it doesn't but it does??), or if it's even necessary for it to sound correct.
- **im probably missing something but i forgot**