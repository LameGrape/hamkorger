import json
import struct
import os


with open("instruments.json", "r") as f:
    instruments = json.load(f)

synths = list(instruments.keys())
categories = list(instruments[synths[0]].keys())


# i cant even lie these classes exists cause its fun writing binary readers and writers
class BinaryReader:
    def __init__(self, stream):
        self.data = stream.read()
        self.index = 0

    def read(self, count):
        result = bytes(self.data[self.index : self.index + count])
        self.index += count
        return result
    def skip(self, count): self.index += count
    def seek(self, offset): self.index = offset
    def position(self): return self.index

    def byte(self): return struct.unpack("<B", self.read(1))[0]
    def sbyte(self): return struct.unpack("<b", self.read(1))[0]
    def short(self): return struct.unpack("<h", self.read(2))[0]
    def ushort(self): return struct.unpack("<H", self.read(2))[0]
    def int(self): return struct.unpack("<i", self.read(4))[0]
    def uint(self): return struct.unpack("<I", self.read(4))[0]
    def long(self): return struct.unpack("<q", self.read(8))[0]
    def ulong(self): return struct.unpack("<Q", self.read(8))[0]

    def bool(self): return struct.unpack("<?", self.read(1))[0]
    def string(self, size): return self.read(size).decode()
    def nullstr(self, max):
        string = self.read(max).decode()
        if "\0" in string: return string[:string.index("\0")]
        return string

class BinaryWriter:
    def __init__(self, stream):
        self.stream = stream

    def write(self, data): self.stream.write(data)
    def pad(self, count): self.stream.write(bytes(0 for i in range(count)))
    def position(self): return self.stream.tell()
    def seek(self, offset): self.stream.seek(offset)

    def byte(self, data): self.write(struct.pack(">B", data))
    def sbyte(self, data): self.write(struct.pack(">b", data))
    def short(self, data): self.write(struct.pack(">h", data))
    def ushort(self, data): self.write(struct.pack(">H", data))
    def int(self, data): self.write(struct.pack(">i", data))
    def uint(self, data): self.write(struct.pack(">I", data))
    def long(self, data): self.write(struct.pack(">q", data))
    def ulong(self, data): self.write(struct.pack(">Q", data))

    def bool(self, data): self.write(struct.pack(">?", data))
    def string(self, data): self.write(data.encode())


# open a .sav file and read out
def getSongs(path):
    if not os.path.isfile(path): return None

    reader = BinaryReader(open(path, "rb"))
    songs = []

    reader.skip(4) # checksum maybe?
    if reader.string(4) != "M01W": return None
    reader.skip(4) # yeah i have no clue but its not important so skip

    # the song names are stored twice? i dont know why but ijust need the names sooo
    for i in range(10):
        song = {
            "modified": reader.bool(),
            "name": reader.nullstr(8),
            "channels": [],
            "blockTempos": [],
            "blockSteps": []
        }
        songs.append(song)
        reader.skip(31) # probably not important, skip

    for i, song in enumerate(songs):
        reader.seek(0x1000 + 0xC000 * i) # thank you korg devs for storing song data at constant offsets

        # channel data
        reader.skip(8) # probably not important, skip

        for i in range(8):
            synth_no = reader.byte()
            category_no = reader.byte()
            inst_no = reader.byte()

            reader.skip(2)

            channel = {
                "attack": reader.byte(),
                "release": reader.byte(),
                "volume": reader.byte(),
                "blocks": [],
                "instrument": (synth_no, category_no, inst_no),
            }
            song["channels"].append(channel)
            reader.skip(48) # probably not important, skip

        reader.skip(62) # probably not important, skip
        song["tempo"] = reader.short()
        song["swing"] = reader.byte()
        song["steps"] = reader.byte()
        reader.skip(4) # probably not important, skip
        musicPos = reader.short() + reader.position()

        for i in range(99):
            song["blockTempos"].append(reader.short())
            song["blockSteps"].append(reader.byte())
            reader.skip(5) # probably not important, skip

        reader.seek(musicPos)
        for i in range(99): ## 99 blocks per 8 channes
            for j in range(8):
                reader.skip(4) # probably not important, skip
                # the channel number is included there but we have that already
                offset = reader.byte() # offset of block (0 is far left)
                reader.skip(1) # offset might actually be a short? i dont care, only goes up to 99 anyways

                noteCount = reader.short()
                if noteCount <= 0: continue # empty :(

                block = {
                    "offset": offset,
                    "notes": []
                }
                for i in range(noteCount):
                    note = {
                        "length": (reader.byte() + 1) / 4, # actual length is multiplied by 4 in the .sav to fit in an integer
                        "velocity": reader.byte(), # 0-15
                        "pitch": reader.byte(), # 140-240
                        "offset": reader.byte() # offset relative to start of the currentblock
                    }
                    block["notes"].append(note)
                song["channels"][j]["blocks"].append(block)

    return songs


# export a song (you should have gotten one ^ up there) to a midi file
# if my midi implementation sucks you can blame http://www.music.mcgill.ca/~ich/classes/mumt306/StandardMIDIfileformat.html
def exportSong(song):
    writer = BinaryWriter(open(f"{song["name"]}.mid", "wb"))

    # midi header
    writer.string("MThd")
    writer.int(6) # need to set the length even though the header is always the same size? this format is goofy
    writer.short(0) # format 0 (only 1 track)
    writer.short(1) # still need to set the track count :(
    writer.short(400) # 400 ticks per quarter note
    # a 1 length M01 note is (i believe) 1/16th beat, so the lowest possible note size is 25 ticks

    notes = []
    lastTempo = song["tempo"]

    offsets = [0]
    for i, steps in enumerate(song["blockSteps"]):
        offsets.append(offsets[i] + (song["steps"] if song["blockSteps"][i] == 0 else song["blockSteps"][i]))

    for i, channel in enumerate(channel for channel in song["channels"]):
        if len(channel["blocks"]) == 0:
            continue
        for block in channel["blocks"]:
            tempo = song["tempo"] if song["blockTempos"][block["offset"]] == 0 else song["blockTempos"][block["offset"]]
            if tempo != lastTempo:
                notes.append((0, offsets[block["offset"]], tempo, -1)) # negative velocity ensures it comes before notes
            lastTempo = tempo

            for note in block["notes"]:
                offset = offsets[block["offset"]]
                swing = ((song["swing"] - 50) / 50) if note["offset"] % 2 == 1 else 0
                velocity = int(min(127, (note["velocity"] / 15 * 127) * (channel["volume"] / 100)))
                notes.append((i, note["offset"] + swing + offset, note["pitch"] - 128, velocity)) # positive velocity for note on
                notes.append((i, note["offset"] + note["length"] + offset, note["pitch"] - 128, 0)) # zero velocity for note off

    notes.sort(key=lambda x: (x[1], x[3])) # sort by time offset, then velocity

    # midi track
    writer.string("MTrk")
    lengthPos = writer.position()
    writer.pad(4) # dont know the length of the data yet, so come back later

    # set the start tempo
    writer.write(bytes((0x00, 0xFF, 0x51, 0x03)))
    writer.write(struct.pack(">I", int(1000**2 / (song["tempo"] / 60)))[1:])
    # midi tempos are stored as "microseconds per beat", not "beats per minute" for some reason

    midiCCBase = 0xB0
    midiAttack = 73
    midiRelease = 72

    def writeMidiCC(channel, control, value):
        writer.write(bytes((0x00, midiCCBase + channel)))
        writer.byte(control)
        # A/R is 0-15 in M01, MIDI CCs are 0-127.
        # Value scaling should be moved if other CCs
        # don't follow this.
        writer.byte(int(value*127/15))

    # set instruments to midi equivalents, if notes exist
    for i in range(8):
        if len(song["channels"][i]["blocks"]) == 0:
            continue
        synth_no, category_no, inst_no = song["channels"][i]["instrument"]
        midi_inst_no = instruments[synths[synth_no]][categories[category_no]][inst_no][1]
        writer.write(bytes((0x00, 0xC0 + i))) # program change
        writer.byte(midi_inst_no) # instrument number

        writeMidiCC(i, midiAttack, song["channels"][i]["attack"])
        writeMidiCC(i, midiRelease, song["channels"][i]["release"])

    lastOffset = 0
    for note in notes:
        writeVarLen((note[1] - lastOffset) * 100, writer) # M01 note offsets > MIDI ticks

        if(note[3] == -1): # tempo change
            writer.write(bytes((0xFF, 0x51, 0x03)))
            writer.write(struct.pack(">I", int(1000**2 / (note[2] / 60)))[1:])
        else: # note
            writer.byte((0x90 if note[3] > 0 else 0x80) + note[0]) # note on/off and channel
            writer.byte(note[2]) # pitch
            writer.byte(note[3]) # velocity

        lastOffset = note[1]

    writer.write(bytes((0x00, 0xFF, 0x2F, 0x00))) # end of track

    length = writer.position() - lengthPos - 4
    writer.seek(lengthPos)
    writer.int(length)  # i told you wed come back


# a special data type is used for variable length integers
# adapted from C code provided by the specification
def writeVarLen(value, writer):
    value = int(value)
    buffer = value & 0x7f
    while (value := value >> 7) > 0:
        buffer <<= 8
        buffer |= 0x80
        buffer += value & 0x7f
    while (True):
        writer.write(struct.pack(">I", buffer)[3:])
        if (buffer & 0x80):
            buffer >>= 8
        else:
            break


if __name__ == "__main__":
    print("---| hamkorger - Korg M01 MIDI extractor |---\n")

    print("Enter the .sav file path:")
    path = input("> ").strip().strip("\"").strip("'")
    songs = getSongs(path)
    if songs is None:
        print("Invalid save file")
        exit(1)

    print("\nEnter the number of the song to export:")
    for i, song in enumerate(songs):
        print(f"- {i + 1}{"*" if song["modified"] else ""}: {song["name"]}")
    selection = int(input("> ")) - 1
    exportSong(songs[selection])

    print(f"Done > {songs[selection]["name"]}.mid")