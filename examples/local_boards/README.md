# A board of the program

`my_board` is not in the catalog of the component. It lies in `components/local-boards/`, a tree
in the layout of `catalog/`: a dev board of the catalog, two modules the catalog does not have (a round
display on QSPI and a 2004 character LCD on a PCF8574, on I2C), and the wires between them. The program
fills the display and writes the name of the board on the first row of the 2004.

```sh
python3 ../../tools/board_select.py my_board .
idf.py build flash monitor
```

`board_select.py` makes the glue beside the data, and the board joins the menu of the boards. The 2004
is not the primary display beside the round one: its use says so in `devices`. A change of the board
that needs another library, as a module added, takes it once `dependencies.lock.my_board` and
`build/my_board` are removed.
