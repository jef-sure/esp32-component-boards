# The level of the sound of a board

How loud a board's speaker is at a given level of samples is a fact of the board,
heard on it: a program's mixer starts at that level (`board_sound_t.mixer_volume`).
This program plays a tone of 441 Hz at levels from 5 to 100 percent of full scale,
each for three seconds, the level in the log and as a bar on the display:

```sh
python3 ../../tools/board_select.py jc8012p4a1c .
idf.py build flash monitor
```

The level that sounds neither faint nor loud goes into the data of the board, as
`config.mixer_volume` of its sound, with the trial in `checked` at the level
`hardware`. It holds for the hardware as the component sets it up: a codec at the
start volume of its data.
