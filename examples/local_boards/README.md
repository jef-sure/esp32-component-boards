# A board of the program

`my_board` is not in the catalog of the component. It lies in `components/local-boards/`, a tree
in the layout of `catalog/`: a dev board of the catalog, a module the catalog does not have, and
the wires between them.

```sh
python3 ../../tools/board_select.py my_board .
idf.py build flash monitor
```

`board_select.py` makes the glue beside the data, and the board joins the menu of the boards.
