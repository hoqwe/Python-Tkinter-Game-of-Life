# Python-Tkinter-Game-of-Life
An interactive Conway's Game of Life with a GUI, built in Python using only Tkinter.

This is what it looks like:

![game_of_life](https://github.com/user-attachments/assets/1720284c-12d6-456e-b657-e8b773c3cd91)

**Requirements?** Python 3.10+, that's all.

**How to run it?** Just run the `game_of_life.py`.

## What is this?
This is Conway's Game of Life - a grid of live and dead cells that evolve according to simple rules:
- A live cell stays alive only with 2 or 3 live neighbors.
- A dead cell becomes alive with exactly 3 live neighbors.

This application is a playground for experimenting with those rules.

## About the performance
Is it laggy? That's ok. Tkinter isn't built for applications like this - ones that involve lots of constant updates. It's designed for simple GUIs with buttons, entry fields, etc., to get user input, do something, and wait while idle. Tkinter struggles to handle something like 100x100 cells updating 60 times per second, so the minimum cell size is set to 10 px to keep the application running at all. Of course, you can change the lower bound to 1 px in the code, but it will run at 0.01 FPS or so, if it even runs.

---

The current implementation uses Tkinter canvas rectangles to render cells, which is OK in terms of performance and easy to use in the code.

A better (maybe the best) approach to implementing Game of Life in Python at high FPS is to use **PyGame** - it can handle 800x800 px canvas with 1 px cells at 60 FPS. Also, PyGame can use the GPU, unlike Tkinter, which runs only on the CPU.

And other approaches:
- **NumPy** (fast next cell states computation) + **Pillow** (fast image generation): about 5x faster than the current approach, but requires installing those libraries.
- Image generation by Tkinter: 2x slower than the current approach, but x2 faster for rendering 1 px cells (which is still unplayable). Also, it requires creating a HUGE string for each frame (e.g., `"{#rrggbb #rrggbb} {#rrggbb #rrggbb}"` - that's just 4 pixels out of 400x400 = 160,000) which then has to be PARSED back by Tkinter. Not worth it.

Source: trust me bro (I checked all of those on my own).

## About the code
The code is all in one file, yes. I use the MVC (Model-View-Controller) pattern to separate logic:
- **Model** - Manages the cell state grid and encapsulates the game logic. I think this part turned out very clean.
- **View** - Defines the widgets and their layout without attaching any behavior. Also kinda clean, though it might be doing a bit too much?
- **Controller** - Connects Model and View by adding behavior to all widgets and handling all user actions. The worst of the three, this monstrosity handles all the things together, and I just left it as is, because I don't know how to do it better.
