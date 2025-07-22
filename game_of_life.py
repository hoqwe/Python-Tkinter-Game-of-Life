"""Conway's Game of Life with a GUI."""

import tkinter as tk
from tkinter import ttk, colorchooser
from random import getrandbits
from time import perf_counter
from colorsys import rgb_to_hsv, hsv_to_rgb


class Tooltip:
    """A tooltip that appears when the user hovers over a widget."""

    MAX_WIDTH = 180
    PADDING = 4

    def __init__(self, widget: tk.Widget, text: str) -> None:
        """Bind the tooltip to the given widget."""
        self.widget = widget
        self.text = text

        widget.bind("<Enter>", self._show_tip)
        widget.bind("<Leave>", self._hide_tip)

    def _show_tip(self, event: tk.Event) -> None:
        """Show the tooltip near the widget.

        The tooltip appears below the widget. Its right edge aligns with
        the horizontal center of the widget. The left edge extends up to
        MAX_WIDTH to the left, depending on the length of the text.
        """
        self.tip_window = tk.Toplevel()
        self.tip_window.overrideredirect(True)

        label = ttk.Label(self.tip_window, text=self.text,
                          font="TkDefaultFont 8", padding=self.PADDING,
                          wraplength=self.MAX_WIDTH - 2 * self.PADDING,
                          background="#222222", foreground="#ffffff",
                          relief="solid")
        label.pack()

        self.tip_window.update_idletasks()
        x = (self.widget.winfo_rootx() + self.widget.winfo_width() // 2
             - self.tip_window.winfo_width())
        y = self.widget.winfo_rooty() + self.widget.winfo_height()
        self.tip_window.geometry(f"+{x}+{y}")

    def _hide_tip(self, event: tk.Event) -> None:
        """Destroy the tooltip window."""
        self.tip_window.destroy()


class FPSTracker:
    """Tracks and averages FPS."""

    def __init__(self) -> None:
        """Initialize FPS tracking variables."""
        self.last_fps_time = None
        self.last_avg_fps_time = None
        self.avg_fps_sum = 0
        self.avg_fps_counter = 0

    def tick(self) -> float | None:
        """Track a frame.

        Should be called once per frame. Returns the average FPS
        accumulated over one second of calls, otherwise returns None.
        """
        now = perf_counter()

        if self.last_fps_time is None:
            self.last_fps_time = now
            return None

        fps = 1 / (now - self.last_fps_time)
        self.last_fps_time = now
        self.avg_fps_sum += fps
        self.avg_fps_counter += 1

        if self.last_avg_fps_time is None:
            self.last_avg_fps_time = now
            return None

        if now - self.last_avg_fps_time >= 1:
            self.last_avg_fps_time = now
            avg_fps = self.avg_fps_sum / self.avg_fps_counter
            self.avg_fps_sum = 0
            self.avg_fps_counter = 0
            return avg_fps

        return None


def adjust_color_brightness(color: str, brightness_adjust: float = 0.1) -> str:
    """Adjust brightness of a '#rrggbb' color by a value from 0 to 1.

    The result is lighter or darker, depending on which direction of
    adjustment gives the greater visual difference.
    """
    r = int(color[1:3], 16) / 255
    g = int(color[3:5], 16) / 255
    b = int(color[5:7], 16) / 255
    h, s, v = rgb_to_hsv(r, g, b)

    # Prevent brightness from going out of bounds
    max_brightness_adjust = max(v, 1 - v)
    brightness_adjust = min(brightness_adjust, max_brightness_adjust)

    if v >= brightness_adjust:
        v -= brightness_adjust
    else:
        v += brightness_adjust

    r, g, b = hsv_to_rgb(h, s, v)
    r = int(r * 255)
    g = int(g * 255)
    b = int(b * 255)

    return f"#{r:02x}{g:02x}{b:02x}"


def get_random_color() -> str:
    """Return a random color in the format '#rrggbb'."""
    return '#' + ''.join(f"{getrandbits(8):02x}" for _ in range(3))


class Cell:
    """Handles cell rendering on the canvas.

    Requires class attributes `canvas`, `cell_size`, and `color_map` to
    be set before instantiation.
    """

    canvas: tk.Canvas | None = None
    cell_size: int | None = None
    color_map: dict[int, str] | None = None

    HIGHLIGHT_COLOR_ADJUST = 0.25  # range: [0, 1]

    def __init__(self, row: int, col: int) -> None:
        """Create a dead cell on the canvas."""
        self.color = self.color_map[0]
        self.highlighted = False

        self.cell_id = self.canvas.create_rectangle(col * self.cell_size,
                                                    row * self.cell_size,
                                                    (col + 1) * self.cell_size,
                                                    (row + 1) * self.cell_size,
                                                    fill=self.color,
                                                    width=0)

    def set_state(self, new_state: int) -> None:
        """Set the state of the cell by coloring it accordingly."""
        self.color = self.color_map[new_state]

        if self.highlighted:
            self.prehighlight_color = self.color
            self.color = adjust_color_brightness(self.color,
                                                 self.HIGHLIGHT_COLOR_ADJUST)

        self.canvas.itemconfigure(self.cell_id, fill=self.color)

    def update_highlight(self, new_highlight_state: bool) -> None:
        """Highlight or unhighlight the cell."""
        if new_highlight_state:
            self.prehighlight_color = self.color
            self.color = adjust_color_brightness(self.color,
                                                 self.HIGHLIGHT_COLOR_ADJUST)
        else:
            self.color = self.prehighlight_color

        self.canvas.itemconfigure(self.cell_id, fill=self.color)
        self.highlighted = new_highlight_state

    def undraw(self) -> None:
        """Remove the cell from the canvas."""
        self.canvas.delete(self.cell_id)


class Model:
    """Model for Conway's Game of Life.

    Manages the cell state grid and encapsulates game logic, including:
    - evolution rules (Game of Life),
    - optional wrapping at edges,
    - trace fading of previously alive cells,
    - dynamic grid resizing,
    - and direct cell state updates.
    """

    def __init__(self, num_rows: int, num_cols: int, live_state: int,
                 wrap: bool, trace: bool) -> None:
        """Initialize the game model."""
        self.num_rows = num_rows
        self.num_cols = num_cols
        self.live_state = live_state
        self.wrap = wrap
        self.trace = trace

        self.cell_states = [[0] * self.num_cols for _ in range(self.num_rows)]

        self.population = 0
        self.total_cells = self.num_rows * self.num_cols

    def randomize(self) -> None:
        """Randomize the grid with a 50% chance of live cells."""
        self.population = 0
        for row in range(self.num_rows):
            for col in range(self.num_cols):
                if getrandbits(1):
                    self.cell_states[row][col] = self.live_state
                    self.population += 1
                else:
                    self.cell_states[row][col] = 0

    def clear(self) -> None:
        """Set all cells to dead."""
        for row in range(self.num_rows):
            for col in range(self.num_cols):
                self.cell_states[row][col] = 0
        self.population = 0

    def step(self) -> None:
        """Advance the cell states by one generation.

        Conway's Game of Life rules:
        - A live cell stays alive only with 2 or 3 live neighbors.
        - A dead cell becomes alive with exactly 3 live neighbors.
        """
        cell_states = [[0] * self.num_cols for _ in range(self.num_rows)]
        population = 0

        for row in range(self.num_rows):
            for col in range(self.num_cols):
                cell_state = self.cell_states[row][col]
                live_neighbors = self._count_live_neighbors(row, col)

                # Apply Game of Life rules to set cell alive
                if (cell_state == self.live_state and 2 <= live_neighbors <= 3
                    or cell_state < self.live_state and live_neighbors == 3):
                    cell_states[row][col] = self.live_state
                    population += 1

                # Fade previously alive cell and preserve faintest trail
                elif self.trace and cell_state:
                    cell_states[row][col] = max(cell_state - 1, 1)

        self.cell_states = cell_states
        self.population = population

    def _count_live_neighbors(self, row: int, col: int) -> int:
        """Count live neighbors around the cell at (row, col)."""
        live_neighbors = 0

        for d_row in (-1, 0, 1):
            for d_col in (-1, 0, 1):
                if d_row == 0 and d_col == 0:
                    continue

                neighbor_row = row + d_row
                neighbor_col = col + d_col

                # If row is out of bounds, skip or wrap
                if not (0 <= neighbor_row < self.num_rows):
                    if not self.wrap:
                        continue
                    neighbor_row %= self.num_rows

                # If column is out of bounds, skip or wrap
                if not (0 <= neighbor_col < self.num_cols):
                    if not self.wrap:
                        continue
                    neighbor_col %= self.num_cols

                if (self.cell_states[neighbor_row][neighbor_col]
                    == self.live_state):
                    live_neighbors += 1

        return live_neighbors

    def toggle_wrap(self) -> None:
        """Toggle the wrap mode."""
        self.wrap = not self.wrap

    def toggle_trace(self) -> None:
        """Toggle the trace mode.

        When disabling, set all faded cells to dead.
        """
        self.trace = not self.trace

        if not self.trace:
            for row in range(self.num_rows):
                for col in range(self.num_cols):
                    if self.cell_states[row][col] < self.live_state:
                        self.cell_states[row][col] = 0

    def adjust_grid_size(self, new_num_rows: int, new_num_cols: int) -> None:
        """Add or remove cells to fit into the new canvas space.

        Existing cells keep their state, and new cells start dead.
        """
        old_num_rows = self.num_rows
        old_num_cols = self.num_cols

        self.num_rows = new_num_rows
        self.num_cols = new_num_cols

        # Adjust rows
        if new_num_rows > old_num_rows:
            for _ in range(old_num_rows, new_num_rows):
                self.cell_states.append([0] * old_num_cols)

        elif new_num_rows < old_num_rows:
            for row in range(old_num_rows - 1, new_num_rows - 1, -1):
                for col in range(old_num_cols):
                    if self.cell_states[row][col] == self.live_state:
                        self.population -= 1
            self.cell_states = self.cell_states[:new_num_rows]

        # Adjust cols
        if new_num_cols > old_num_cols:
            for row in range(new_num_rows):
                self.cell_states[row].extend(
                    [0] * (new_num_cols - old_num_cols))

        elif new_num_cols < old_num_cols:
            for row in range(new_num_rows):
                for col in range(old_num_cols - 1, new_num_cols - 1, -1):
                    if self.cell_states[row][col] == self.live_state:
                        self.population -= 1
                self.cell_states[row] = self.cell_states[row][:new_num_cols]

        self.total_cells = self.num_rows * self.num_cols

    def set_cells_state(self, cells: list[tuple[int, int]], state: bool
                        ) -> None:
        """Set the given cells to alive or dead."""
        for row, col in cells:
            if state and self.cell_states[row][col] != self.live_state:
                self.cell_states[row][col] = self.live_state
                self.population += 1

            elif not state and self.cell_states[row][col] != 0:
                if self.cell_states[row][col] == self.live_state:
                    self.population -= 1
                self.cell_states[row][col] = 0

    def get_cell_states(self) -> list[list[int]]:
        """Get the cell states."""
        return self.cell_states


class View(tk.Tk):
    """UI layout for Conway's Game of Life.

    Defines the widgets and their layout without attaching any behavior.
    """

    CANVAS_BACKGROUND_COLOR_ADJUST = 0.1  # range: [0, 1]

    def __init__(self, canvas_width: int, canvas_height: int, cell_size: int,
                 dead_cell_color: str, live_cell_color: str, grid: bool,
                 trace: bool, live_state: int) -> None:
        """Create and layout all the widgets."""
        super().__init__()
        self.title("Conway's Game of Life")

        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.cell_size = cell_size
        self.dead_cell_color = dead_cell_color
        self.live_cell_color = live_cell_color
        self.grid = grid
        self.trace = trace
        self.live_state = live_state

        self.num_rows = self.canvas_height // self.cell_size
        self.num_cols = self.canvas_width // self.cell_size

        self.grid_lines = []
        self.help_window_is_open = False

        self._precompute_color_map()

        self._make_grid_canvas()
        self._make_ui()

    def _make_grid_canvas(self) -> None:
        """Create the canvas with a grid of cells."""
        self.canvas = tk.Canvas(
            width=self.canvas_width,
            height=self.canvas_height,
            highlightthickness=0,
            bg=adjust_color_brightness(self.dead_cell_color,
                                       self.CANVAS_BACKGROUND_COLOR_ADJUST))
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self._create_cells()
        self._create_grid_lines()

    def _create_cells(self) -> None:
        """Create the cells on the canvas."""
        Cell.canvas = self.canvas
        Cell.cell_size = self.cell_size
        Cell.color_map = self.color_map

        self.cells = [[None] * self.num_cols for _ in range(self.num_rows)]
        for row in range(self.num_rows):
            for col in range(self.num_cols):
                self.cells[row][col] = Cell(row, col)

    def _make_ui(self) -> None:
        """Create the UI on the right of the canvas."""
        self._make_ui_frames()

        self._make_controls_section(self.upper_ui_frame, row=0)
        self._make_appearance_section(self.upper_ui_frame, row=1)
        self._make_drawing_tool_section(self.upper_ui_frame, row=2)
        self._make_statistics_section(self.bottom_ui_frame, row=0)
        self._make_bottom_buttons_section(self.bottom_ui_frame, row=1)

    def _make_ui_frames(self) -> None:
        """Create the UI frames (invisible layout containers)."""
        # Main UI frame
        main_ui_frame = ttk.Frame(padding=4)
        main_ui_frame.grid(row=0, column=1, sticky="nsew")
        main_ui_frame.rowconfigure(0, weight=1)

        # Upper UI frame
        self.upper_ui_frame = ttk.Frame(main_ui_frame)
        self.upper_ui_frame.grid(row=0, column=0, sticky="nsew")
        self.upper_ui_frame.columnconfigure(0, weight=1)

        # Bottom UI frame
        self.bottom_ui_frame = ttk.Frame(main_ui_frame)
        self.bottom_ui_frame.grid(row=1, column=0, sticky="nsew")
        self.bottom_ui_frame.columnconfigure(0, weight=1)

    def _make_controls_section(self, frame: ttk.Frame, row: int) -> None:
        """Create the controls section."""
        controls_frame = ttk.LabelFrame(frame, text="Controls", padding=4)
        controls_frame.grid(row=row, column=0, sticky="ew", pady=(0, 4))

        # Pause/play button
        self.pause_play_button = ttk.Button(controls_frame)
        self.pause_play_button.grid(row=0, column=0, sticky="ew")

        # Step button
        self.step_button = ttk.Button(controls_frame, text="Step")
        self.step_button.grid(row=0, column=1, sticky="ew")

        # Clear button
        self.clear_button = ttk.Button(controls_frame, text="Clear")
        self.clear_button.grid(row=1, column=0, sticky="ew")

        # Randomize button
        self.randomize_button = ttk.Button(controls_frame, text="Randomize")
        self.randomize_button.grid(row=1, column=1, sticky="ew")

        # Speed scale
        speed_scale_frame = ttk.Frame(controls_frame)
        speed_scale_frame.grid(row=2, column=0, columnspan=2, sticky="ew")
        speed_scale_frame.columnconfigure(1, weight=1)

        speed_scale_label = ttk.Label(speed_scale_frame, text="Speed (FPS):")
        speed_scale_label.grid(row=0, column=0)

        self.speed_scale = ttk.Scale(speed_scale_frame, length=0)
        self.speed_scale.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        self.speed_scale_value = ttk.Label(speed_scale_frame, anchor="e")
        self.speed_scale_value.grid(row=0, column=2, padx=(4, 0))

        # Current FPS
        current_fps_frame = ttk.Frame(controls_frame)
        current_fps_frame.grid(row=3, column=0, columnspan=2, sticky="ew")
        current_fps_frame.columnconfigure(1, weight=1)

        current_fps_label = ttk.Label(current_fps_frame, text="Current FPS:")
        current_fps_label.grid(row=0, column=0)

        self.current_fps_value = ttk.Label(current_fps_frame, text="-")
        self.current_fps_value.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        current_fps_help = ttk.Label(current_fps_frame, text="(?)", anchor="e")
        current_fps_help.grid(row=0, column=2)
        current_fps_help_text = (
            "Note: The frame rate may drop slightly below the target when "
            "there's no user interaction, due to OC application priorities."
            )
        Tooltip(current_fps_help, current_fps_help_text)

        # Edge wrapping checkbutton
        self.wrap_checkbutton = ttk.Checkbutton(controls_frame,
                                                text="Edge Wrapping")
        self.wrap_checkbutton.grid(row=4, column=0, columnspan=2, sticky="w")

    def _make_appearance_section(self, frame: ttk.Frame, row: int) -> None:
        """Create the appearance section."""
        appearance_frame = ttk.LabelFrame(frame, text="Appearance", padding=4)
        appearance_frame.grid(row=row, column=0, sticky="ew", pady=(0, 4))
        appearance_frame.columnconfigure(0, weight=1)

        # Live cell color picker
        live_cell_color_frame = ttk.Frame(appearance_frame)
        live_cell_color_frame.grid(row=0, column=0, sticky="w")

        self.live_cell_color_sample = tk.Canvas(live_cell_color_frame,
                                                width=11, height=11,
                                                relief="solid", bd=1)
        self.live_cell_color_sample.grid(row=0, column=0)

        live_cell_color_label = ttk.Label(live_cell_color_frame,
                                          text="Live Cell Color")
        live_cell_color_label.grid(row=0, column=1, sticky="w")

        # Dead cell color picker
        dead_cell_color_frame = ttk.Frame(appearance_frame)
        dead_cell_color_frame.grid(row=1, column=0, sticky="w")

        self.dead_cell_color_sample = tk.Canvas(dead_cell_color_frame,
                                                width=11, height=11,
                                                relief="solid", bd=1)
        self.dead_cell_color_sample.grid(row=0, column=0)

        dead_cell_color_label = ttk.Label(dead_cell_color_frame,
                                          text="Dead Cell Color")
        dead_cell_color_label.grid(row=0, column=1, sticky="w")

        # Grid checkbutton
        self.grid_checkbutton = ttk.Checkbutton(appearance_frame, text="Grid")
        self.grid_checkbutton.grid(row=0, column=1, sticky="w")

        # Trace checkbutton
        self.trace_checkbutton = ttk.Checkbutton(appearance_frame,
                                                 text="Trace")
        self.trace_checkbutton.grid(row=1, column=1, sticky="w")

        # Cell size scale
        cell_size_frame = ttk.Frame(appearance_frame)
        cell_size_frame.grid(row=2, column=0, columnspan=2, sticky="ew")
        cell_size_frame.columnconfigure(1, weight=1)

        cell_size_label = ttk.Label(cell_size_frame, text="Cell Size (px):")
        cell_size_label.grid(row=0, column=0)

        self.cell_size_scale = ttk.Scale(cell_size_frame, length=0)
        self.cell_size_scale.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        self.cell_size_value = ttk.Label(cell_size_frame, anchor="e")
        self.cell_size_value.grid(row=0, column=2, padx=(4, 0))

    def _make_drawing_tool_section(self, frame: ttk.Frame, row: int) -> None:
        """Create the drawing tool section."""
        drawing_tool_frame = ttk.LabelFrame(frame, text="Drawing Tool",
                                            padding=4)
        drawing_tool_frame.grid(row=row, column=0, sticky="ew", pady=(0, 4))
        drawing_tool_frame.columnconfigure(0, weight=1)

        # Shape combobox
        shape_label = ttk.Label(drawing_tool_frame, text="Shape:")
        shape_label.grid(row=0, column=0, sticky="w", pady=(0, 4))

        self.shape_combobox = ttk.Combobox(drawing_tool_frame, width=12,
                                           state="readonly")
        self.shape_combobox.grid(row=0, column=1, sticky="e", pady=(0, 4))

        # Remove combobox text selection after any combobox interaction
        self.shape_combobox.bind("<FocusIn>", lambda event: self.focus_set())

        # Control tips label
        control_tips_label = ttk.Label(
            drawing_tool_frame, text="LMB: Create Cells\nRMB: Remove Cells")
        control_tips_label.grid(row=1, column=0, columnspan=2, sticky="w")

    def _make_statistics_section(self, frame: ttk.Frame, row: int) -> None:
        """Create the statistics section."""
        statistics_frame = ttk.LabelFrame(frame, text="Statistics", padding=4)
        statistics_frame.grid(row=row, column=0, sticky="ew", pady=(0, 4))

        # Generation
        generation_label = ttk.Label(statistics_frame, text="Generation:")
        generation_label.grid(row=0, column=0, sticky="w")

        self.generation_value = ttk.Label(statistics_frame)
        self.generation_value.grid(row=0, column=1, sticky="w")

        # Population
        population_label = ttk.Label(statistics_frame, text="Population:")
        population_label.grid(row=1, column=0, sticky="nw")

        self.population_value = ttk.Label(statistics_frame)
        self.population_value.grid(row=1, column=1, sticky="w")

    def _make_bottom_buttons_section(self, frame: ttk.Frame, row: int) -> None:
        """Create the bottom buttons section."""
        bottom_buttons_frame = ttk.Frame(frame)
        bottom_buttons_frame.grid(row=row, column=0, sticky="ew")
        bottom_buttons_frame.columnconfigure(0, weight=1)

        # Help button
        self.help_button = ttk.Button(bottom_buttons_frame, text="Help...",
                                      width=8)
        self.help_button.grid(row=0, column=1)

        # Exit button
        self.exit_button = ttk.Button(bottom_buttons_frame, text="Exit")
        self.exit_button.grid(row=0, column=2)

    def _precompute_color_map(self) -> None:
        """Precompute a color map using linear interpolation.

        A color map is a dictionary that maps cell states (from 0, dead,
        to `live_state`, alive) to corresponding interpolated colors.
        """

        def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
            """Convert a hex color '#rrggbb' to an (r, g, b) tuple."""
            return tuple(int(hex_color[i + 1 : i + 3], 16) for i in (0, 2, 4))

        def rgb_to_hex(rgb_color: tuple[int, int, int]) -> str:
            """Convert an (r, g, b) tuple to a hex color '#rrggbb'."""
            r, g, b = rgb_color
            return f"#{r:02x}{g:02x}{b:02x}"

        self.color_map = {
            0: self.dead_cell_color, self.live_state: self.live_cell_color
            }

        dead_cell_color_rgb = hex_to_rgb(self.dead_cell_color)
        live_cell_color_rgb = hex_to_rgb(self.live_cell_color)

        for cell_state in range(1, self.live_state):
            t = cell_state / self.live_state  # Interpolation ratio
            interpolated_color = tuple(
                int(a + (b - a) * t)
                for a, b in zip(dead_cell_color_rgb, live_cell_color_rgb))

            self.color_map[cell_state] = rgb_to_hex(interpolated_color)

        Cell.color_map = self.color_map

    def update_all_cells(self, cell_states: list[list[int]]) -> None:
        """Update the state of all cells based on a 2D list."""
        for row in range(self.num_rows):
            for col in range(self.num_cols):
                cell = self.cells[row][col]
                cell.set_state(cell_states[row][col])

    def update_given_cells(self, cells: list[tuple[int, int]], state: bool
                           ) -> None:
        """Update the state of the given cells based on coordinates."""
        for row, col in cells:
            cell = self.cells[row][col]
            cell.set_state(self.live_state if state else 0)

    def change_cells_color(self, state: bool, color: str) -> None:
        """Change the color of dead or live cells."""
        if state:
            self.live_cell_color = color
        else:
            self.dead_cell_color = color

        self._precompute_color_map()
        Cell.color_map = self.color_map

    def update_grid_lines_color(self) -> None:
        """Update the color of grid lines.

        The color of grid lines is in the middle of the dead and live
        cell colors.
        """
        for line in self.grid_lines:
            self.canvas.itemconfig(line,
                                   fill=self.color_map[self.live_state // 2])

    def set_cells_highlight(self, cells: list[tuple[int, int]], state: bool
                            ) -> None:
        """Highlight or unhighlight given cells."""
        for row, col in cells:
            cell = self.cells[row][col]
            cell.update_highlight(state)

    def adjust_grid_size(self, new_num_rows: int, new_num_cols: int) -> None:
        """Add or remove cells to fit into the new canvas space.

        Existing cells keep their state, and new cells start dead.
        """
        old_num_rows = self.num_rows
        old_num_cols = self.num_cols

        self.num_rows = new_num_rows
        self.num_cols = new_num_cols

        # Adjust rows
        if new_num_rows > old_num_rows:
            for row in range(old_num_rows, new_num_rows):
                self.cells.append([None] * old_num_cols)
                for col in range(old_num_cols):
                    self.cells[row][col] = Cell(row, col)

        elif new_num_rows < old_num_rows:
            for row in range(old_num_rows - 1, new_num_rows - 1, -1):
                for col in range(old_num_cols):
                    self.cells[row][col].undraw()
            self.cells = self.cells[:new_num_rows]

        # Adjust cols
        if new_num_cols > old_num_cols:
            for row in range(new_num_rows):
                for col in range(old_num_cols, new_num_cols):
                    self.cells[row].append(Cell(row, col))

        elif new_num_cols < old_num_cols:
            for row in range(new_num_rows):
                for col in range(old_num_cols - 1, new_num_cols - 1, -1):
                    self.cells[row][col].undraw()
                self.cells[row] = self.cells[row][:new_num_cols]

        self.adjust_grid_lines()

    def adjust_cell_size(self, new_num_rows: int, new_num_cols: int,
                         new_cell_size: int) -> None:
        """Adjust the cell size."""
        self.cell_size = new_cell_size

        # Move existing cells
        for row in range(self.num_rows):
            for col in range(self.num_cols):
                self.canvas.coords(self.cells[row][col].cell_id,
                                   col * self.cell_size,
                                   row * self.cell_size,
                                   (col + 1) * self.cell_size,
                                   (row + 1) * self.cell_size)

        # Remove/add cells
        Cell.cell_size = self.cell_size
        self.adjust_grid_size(new_num_rows, new_num_cols)

    def _create_grid_lines(self) -> None:
        """Create grid lines, either visible or hidden."""
        state = "normal" if self.grid else "hidden"

        # Draw vertical lines
        for col in range(self.num_cols):
            line_id = self.canvas.create_line(
                col * self.cell_size,
                0,
                col * self.cell_size,
                self.num_rows * self.cell_size,
                fill=self.color_map[self.live_state // 2],
                state=state)
            self.grid_lines.append(line_id)

        # Draw horizontal lines
        for row in range(self.num_rows):
            line_id = self.canvas.create_line(
                0,
                row * self.cell_size,
                self.num_cols * self.cell_size,
                row * self.cell_size,
                fill=self.color_map[self.live_state // 2],
                state=state)
            self.grid_lines.append(line_id)

    def toggle_grid_lines(self) -> None:
        """Turn on or off the grid lines."""
        self.grid = not self.grid
        state = "normal" if self.grid else "hidden"
        for grid_line_id in self.grid_lines:
            self.canvas.itemconfigure(grid_line_id, state=state)

    def adjust_grid_lines(self) -> None:
        """Add or remove grid lines to fit into the new canvas space."""
        while self.grid_lines:
            self.canvas.delete(self.grid_lines.pop())

        self._create_grid_lines()

    def create_help_window(self) -> None:
        """Create a help window with rules and keybinds.

        The close button is already associated with a command, since the
        help window is purely visual and does not affect the gameplay.
        """
        # Prevent opening more than one window
        if self.help_window_is_open:
            self.help_window.deiconify()
            return

        self.help_window = tk.Toplevel()
        self.help_window.focus_set()
        self.help_window_is_open = True

        self.help_window.title("Conway's Game of Life - Help")
        self.help_window.resizable(False, False)

        # Help window frame
        help_window_frame = ttk.Frame(self.help_window, padding=4)
        help_window_frame.pack()

        # Rules frame
        rules_frame = ttk.LabelFrame(help_window_frame, text="Rules",
                                     padding=4)
        rules_frame.pack(fill="x", pady=(0, 4))

        rules_text = (
            "This is Conway's Game of Life - a grid of live and dead cells\n"
            "that evolve according to simple rules:\n\n"
            "- A live cell stays alive only with 2 or 3 live neighbors.\n"
            "- A dead cell becomes alive with exactly 3 live neighbors."
            )
        ttk.Label(rules_frame, text=rules_text).pack()

        # Keybinds frame
        keybinds_frame = ttk.LabelFrame(help_window_frame, text="Keybinds",
                                        padding=4)
        keybinds_frame.pack(fill="x", pady=(0, 4))
        keybinds_frame.columnconfigure(0, weight=1)
        keybinds_frame.columnconfigure(1, weight=1)

        keybinds = [
            ("Play/Pause", "Space"),
            ("Step", "S"),
            ("Clear", "C"),
            ("Randomize", "R"),
            ("Toggle Edge Wrapping", "W"),
            ("Toggle Grid", "G"),
            ("Toggle Trace", "T"),
            ("Cycle Shapes", "Mouse Scroll"),
            ("Exit", "Esc")
            ]
        for row, (action, key) in enumerate(keybinds):
            bg = "#dddddd" if row % 2 == 0 else "#ffffff"
            ttk.Label(keybinds_frame, text=action, background=bg
                      ).grid(row=row, column=0, sticky="ew")
            ttk.Label(keybinds_frame, text=key, anchor="c", background=bg
                      ).grid(row=row, column=1, sticky="ew")

        # Close button
        ttk.Button(help_window_frame, text="Close",
                   command=self._close_help_window).pack(side="right")

        self.help_window.protocol("WM_DELETE_WINDOW", self._close_help_window)
        self.help_window.bind("<Escape>", self._close_help_window)

    def _close_help_window(self, event: tk.Event | None = None) -> None:
        """Close the help window."""
        self.help_window.destroy()
        self.help_window_is_open = False

    def main(self) -> None:
        """Mainloop."""
        self.mainloop()


class Controller:
    """Controller for Conway's Game of Life.

    Connects Model and View by adding behavior to all widgets and
    handling all user actions.
    """

    MIN_FPS = 1
    MAX_FPS = 60
    MIN_CELL_SIZE = 10
    MAX_CELL_SIZE = 100

    def __init__(self) -> None:
        """Initialize the default settings and start the game loop."""
        # Controls
        self.running = False
        self.target_fps = 60
        self.wrap = True

        # Appearance
        self.canvas_width = 500
        self.canvas_height = 500
        self.cell_size = 10
        self.dead_cell_color = get_random_color()
        self.live_cell_color = get_random_color()
        self.grid = False
        self.trace = True
        self.live_state = 16  # should be > 1

        # Drawing Tool
        self.shapes = {
            "Cell": [
                (0, 0)
                ],
            "Glider": [
                (2, 0), (2, 1), (2, 2), (1, 2), (0, 1)
                ],
            "Glider gun": [
                (4, 0), (5, 0), (4, 1), (5, 1),
                (4, 10), (5, 10), (6, 10), (3, 11), (7, 11), (2, 12), (8, 12),
                (2, 13), (8, 13), (5, 14), (3, 15), (7, 15), (4, 16), (5, 16),
                (6, 16), (5, 17),
                (2, 20), (3, 20), (4, 20), (2, 21), (3, 21), (4, 21), (1, 22),
                (5, 22), (0, 24), (1, 24), (5, 24), (6, 24),
                (2, 34), (3, 34), (2, 35), (3, 35)
                ],
            "Heart": [
                (0, 2), (0, 3), (1, 4), (0, 5), (0, 6), (1, 7), (2, 8), (3, 8),
                (4, 8), (5, 7), (6, 6), (7, 5), (8, 4), (7, 3), (6, 2), (5, 1),
                (4, 0), (3, 0), (2, 0), (1, 1)
                ]
            }
        self.shape = "Cell"

        self.delay_ms = int(1 / self.target_fps * 1000)
        self.num_rows = self.canvas_height // self.cell_size
        self.num_cols = self.canvas_width // self.cell_size
        self.fps_tracker = FPSTracker()

        self.previous_cell = None
        self.highlighted_cells = []
        self.generation = 0

        self.view = View(self.canvas_width, self.canvas_height, self.cell_size,
                         self.dead_cell_color, self.live_cell_color, self.grid,
                         self.trace, self.live_state)
        self.model = Model(self.num_rows, self.num_cols, self.live_state,
                           self.wrap, self.trace)

        self._configure_widgets()
        self._bind_keys()
        self._bind_canvas_events()
        self.step()

    def _bind_keys(self) -> None:
        """Bind the keys and set the appropriate underlines."""
        self.view.bind("<space>", self.toggle_running)
        self.view.bind("<s>", self.single_step)
        self.view.bind("<c>", self.clear)
        self.view.bind("<r>", self.randomize)
        self.view.bind("<w>", self.toggle_wrap)
        self.view.bind("<g>", self.toggle_grid)
        self.view.bind("<t>", self.toggle_trace)
        self.view.bind("<Escape>", lambda event: self.view.destroy())

        # Underlines
        self.view.step_button.config(underline=0)
        self.view.clear_button.config(underline=0)
        self.view.randomize_button.config(underline=0)
        self.view.wrap_checkbutton.config(underline=5)
        self.view.grid_checkbutton.config(underline=0)
        self.view.trace_checkbutton.config(underline=0)

        # Disable focus state for proper space behavior
        self.view.pause_play_button.config(takefocus=False)
        self.view.step_button.config(takefocus=False)
        self.view.clear_button.config(takefocus=False)
        self.view.randomize_button.config(takefocus=False)
        self.view.wrap_checkbutton.config(takefocus=False)
        self.view.grid_checkbutton.config(takefocus=False)
        self.view.trace_checkbutton.config(takefocus=False)
        self.view.help_button.config(takefocus=False)
        self.view.exit_button.config(takefocus=False)

    def _bind_canvas_events(self) -> None:
        """Bind the events to the canvas."""
        self.view.canvas.bind("<MouseWheel>", self._cycle_through_shapes)
        self.view.canvas.bind("<Configure>", self.adjust_grid_size)
        self.view.canvas.bind("<Button>", self._mouse_click_handler)
        self.view.canvas.bind("<Motion>", self._mouse_motion_handler)
        self.view.canvas.bind("<Leave>", self._clear_hover_state)

    def _configure_widgets(self) -> None:
        """Configure all widgets with initial values and commands."""
        # Pause/play button
        self.view.pause_play_button.config(
            text="Pause" if self.running else "Play",
            command=self.toggle_running)

        # Step button
        self.view.step_button.config(command=self.single_step)

        # Clear button
        self.view.clear_button.config(command=self.clear)

        # Randomize button
        self.view.randomize_button.config(command=self.randomize)

        # Speed scale
        self.view.speed_scale_value.config(text=self.target_fps)
        self.view.speed_scale.config(from_=self.MIN_FPS, to=self.MAX_FPS,
                                     value=self.target_fps,
                                     command=self.update_target_fps)

        # Edge wrapping checkbutton
        self.wrap_checkbutton_var = tk.BooleanVar(value=self.wrap)
        self.view.wrap_checkbutton.config(variable=self.wrap_checkbutton_var,
                                          command=self.toggle_wrap)

        # Live cell color
        self.view.live_cell_color_sample.config(bg=self.live_cell_color)
        self.view.live_cell_color_sample.bind(
            "<Button-1>", lambda event: self.change_cells_color(event,
                                                                state=True))

        # Dead cell color
        self.view.dead_cell_color_sample.config(bg=self.dead_cell_color)
        self.view.dead_cell_color_sample.bind(
            "<Button-1>", lambda event: self.change_cells_color(event,
                                                                state=False))

        # Grid checkbutton
        self.grid_checkbutton_var = tk.BooleanVar(value=self.grid)
        self.view.grid_checkbutton.config(variable=self.grid_checkbutton_var,
                                          command=self.toggle_grid)

        # Trace checkbutton
        self.trace_checkbutton_var = tk.BooleanVar(value=self.trace)
        self.view.trace_checkbutton.config(variable=self.trace_checkbutton_var,
                                           command=self.toggle_trace)

        # Cell size
        self.view.cell_size_value.config(text=self.cell_size)
        self.view.cell_size_scale.config(from_=self.MIN_CELL_SIZE,
                                         to=self.MAX_CELL_SIZE,
                                         value=self.cell_size,
                                         command=self.adjust_cell_size)

        # Shape combobox
        self.shape_combobox_var = tk.StringVar(value=self.shape)
        self.view.shape_combobox.config(values=list(self.shapes),
                                        textvariable=self.shape_combobox_var)
        self.view.shape_combobox.bind(
            "<<ComboboxSelected>>",
            lambda event: self.update_shape(self.view.shape_combobox.get()))

        # Generation
        self.view.generation_value.config(text=self.generation)

        # Population
        self._update_population_label_value()

        # Help button
        self.view.help_button.config(command=self.view.create_help_window)

        # Exit button
        self.view.exit_button.config(command=self.view.destroy)

    def toggle_running(self, event: tk.Event | None = None) -> None:
        """Toggle the game state on or off."""
        self.running = not self.running
        self.view.pause_play_button.config(
            text="Pause" if self.running else "Play")

    def step(self, single_step: bool = False) -> None:
        """Advance the game in a loop or by one generation."""
        if self.running or single_step:
            self.model.step()
            self.view.update_all_cells(self.model.get_cell_states())

            self.generation += 1
            self.view.generation_value.config(text=self.generation)

            self._update_population_label_value()

        if not single_step:
            fps = self.fps_tracker.tick()
            if fps is not None:
                self.view.current_fps_value.config(text=f"{fps:.2f}")

            self.view.after(self.delay_ms, self.step)

    def single_step(self, event: tk.Event | None = None) -> None:
        """Advance the game by one generation."""
        self.step(single_step=True)

    def clear(self, event: tk.Event | None = None) -> None:
        """Set all cells to dead."""
        self.model.clear()
        self.view.update_all_cells(self.model.get_cell_states())

        self.generation = 0
        self.view.generation_value.config(text=self.generation)

        self._update_population_label_value()

    def randomize(self, event: tk.Event | None = None) -> None:
        """Randomize the cells."""
        self.model.randomize()
        self.view.update_all_cells(self.model.get_cell_states())

        self.generation = 0
        self.view.generation_value.config(text=self.generation)

        self._update_population_label_value()

    def update_target_fps(self, new_target_fps: str) -> None:
        """Update the target FPS."""
        self.target_fps = int(float(new_target_fps))
        self.delay_ms = int(1 / self.target_fps * 1000)
        self.view.speed_scale_value.config(text=self.target_fps)

    def toggle_wrap(self, event: tk.Event | None = None) -> None:
        """Toggle the wrap on or off."""
        self.wrap = not self.wrap
        self.model.toggle_wrap()
        self.wrap_checkbutton_var.set(self.wrap)

        # Refresh highlight on keybind for proper wrap-awareness
        if event:
            row = event.y // self.cell_size
            col = event.x // self.cell_size

            if 0 <= row < self.num_rows and 0 <= col < self.num_cols:
                self._unhighlight_highlighted_cells()
                affected_cells = self._get_affected_pixels(
                    row, col, self.shapes[self.shape])
                self._highlight_cells(affected_cells)

    def change_cells_color(self, event: tk.Event, state: bool) -> None:
        """Change color of the cells.

        Display a color palette and change cells of the specified state
        to the chosen color.
        """
        initial_color = self.live_cell_color if state else self.dead_cell_color
        color = colorchooser.askcolor(initial_color)[1]

        if color:
            if state:
                self.live_cell_color = color
                self.view.live_cell_color_sample.config(bg=color)
            else:
                self.dead_cell_color = color
                self.view.dead_cell_color_sample.config(bg=color)
                self.view.canvas.config(bg=adjust_color_brightness(
                    color, self.view.CANVAS_BACKGROUND_COLOR_ADJUST))

            self.view.change_cells_color(state, color)
            self.view.update_all_cells(self.model.get_cell_states())

            self.view.update_grid_lines_color()

    def toggle_grid(self, event: tk.Event | None = None) -> None:
        """Toggle the grid on or off."""
        self.grid = not self.grid
        self.view.toggle_grid_lines()
        self.grid_checkbutton_var.set(self.grid)

    def toggle_trace(self, event: tk.Event | None = None) -> None:
        """Toggle the trace on or off."""
        self.trace = not self.trace
        self.model.toggle_trace()
        self.trace_checkbutton_var.set(self.trace)
        if not self.trace:
            self.view.update_all_cells(self.model.get_cell_states())

    def adjust_cell_size(self, new_cell_size: str) -> None:
        """Adjust the cell size."""
        self.cell_size = int(float(new_cell_size))
        self.view.cell_size_value.config(text=self.cell_size)

        self.num_rows = self.canvas_height // self.cell_size
        self.num_cols = self.canvas_width // self.cell_size
        self.model.adjust_grid_size(self.num_rows, self.num_cols)
        self.view.adjust_cell_size(self.num_rows, self.num_cols,
                                   self.cell_size)

        self._update_population_label_value()

    def adjust_grid_size(self, event: tk.Event) -> None:
        """Adjust the grid size."""
        self.canvas_height = event.height
        self.canvas_width = event.width
        self.num_rows = event.height // self.cell_size
        self.num_cols = event.width // self.cell_size
        self.model.adjust_grid_size(self.num_rows, self.num_cols)
        self.view.adjust_grid_size(self.num_rows, self.num_cols)

        self._update_population_label_value()

    def update_shape(self, shape: str) -> None:
        """Update the shape of the drawing tool."""
        self.shape = shape

    def _cycle_through_shapes(self, event: tk.Event) -> None:
        """Cycle the shapes on scroll and update the cell highlights."""
        # Cycle to the next/previous shape
        delta = 1 if event.delta > 0 else -1
        keys = list(self.shapes)
        self.shape = keys[(keys.index(self.shape) + delta) % len(self.shapes)]
        self.shape_combobox_var.set(self.shape)

        # Update highlight
        row = event.y // self.cell_size
        col = event.x // self.cell_size

        if 0 <= row < self.num_rows and 0 <= col < self.num_cols:
            affected_cells = self._get_affected_pixels(row, col,
                                                       self.shapes[self.shape])

            self._unhighlight_highlighted_cells()
            self._highlight_cells(affected_cells)

    def _mouse_click_handler(self, event: tk.Event) -> None:
        """Set the cell(s) live on left click or dead on right click."""
        row = event.y // self.cell_size
        col = event.x // self.cell_size

        if 0 <= row < self.num_rows and 0 <= col < self.num_cols:
            affected_cells = self._get_affected_pixels(row, col,
                                                       self.shapes[self.shape])

            # Left click: set the cell(s) alive
            if event.num == 1:
                self.model.set_cells_state(affected_cells, state=True)
                self.view.update_given_cells(affected_cells, state=True)

            # Right click: set the cell(s) dead
            elif event.num == 3:
                self.model.set_cells_state(affected_cells, state=False)
                self.view.update_given_cells(affected_cells, state=False)

            self._update_population_label_value()

    def _mouse_motion_handler(self, event: tk.Event) -> None:
        """Set the cell(s) live on left drag or dead on right drag."""
        row = event.y // self.cell_size
        col = event.x // self.cell_size

        # If the cursor is within the grid
        if 0 <= row < self.num_rows and 0 <= col < self.num_cols:
            cell = (row, col)
            # If the cursor has moved to another cell
            if cell != self.previous_cell:
                self.previous_cell = cell

                affected_cells = self._get_affected_pixels(
                    row, col, self.shapes[self.shape])

                self._unhighlight_highlighted_cells()

                # Keep only mouse button bits (0xff00) to ignore
                # modifiers like Shift (0x0001), Num Lock (0x0010), etc.
                state = event.state & 0xff00

                # Left click drag: set the cell(s) alive
                if state == 0x0100:
                    self.model.set_cells_state(affected_cells, state=True)
                    self.view.update_given_cells(affected_cells, state=True)

                # Right click drag: set the cell(s) dead
                elif state == 0x0400:
                    self.model.set_cells_state(affected_cells, state=False)
                    self.view.update_given_cells(affected_cells, state=False)

                self._update_population_label_value()
                self._highlight_cells(affected_cells)

        # If the cursor is outside the grid
        else:
            self._clear_hover_state()

    def _highlight_cells(self, cells: list[tuple[int, int]]) -> None:
        """Highlight the given cells."""
        self.view.set_cells_highlight(cells, state=True)
        self.highlighted_cells = cells

    def _unhighlight_highlighted_cells(self) -> None:
        """Unhighlight the highlighted cells."""
        self.view.set_cells_highlight(self.highlighted_cells, state=False)
        self.highlighted_cells = []

    def _clear_hover_state(self, event: tk.Event | None = None) -> None:
        """Clear the state of the last cell visited by the mouse."""
        self._unhighlight_highlighted_cells()
        self.previous_cell = None

    def _get_affected_pixels(self, row: int, col: int,
                             figure: list[tuple[int, int]]
                             ) -> list[tuple[int, int]]:
        """Get affected pixels for a figure at a specific location."""
        affected_pixels = []

        for d_row, d_col in figure:
            new_row = row + d_row
            new_col = col + d_col

            # If the figure pixel within the grid bounds
            if 0 <= new_row < self.num_rows and 0 <= new_col < self.num_cols:
                affected_pixels.append((new_row, new_col))

            # If the figure pixel outside the grid and wrap is enabled
            elif self.wrap:
                affected_pixels.append((new_row % self.num_rows,
                                        new_col % self.num_cols))

        return affected_pixels

    def _update_population_label_value(self) -> None:
        """Update the population value (e.g., '42/54 (77.8%)')."""
        total_cells = self.model.total_cells
        population = self.model.population

        # Prevent division by zero
        if total_cells == 0:
            population_percentage = 0.0
        else:
            population_percentage = (population / total_cells * 100)

        population_value = (
            f"{population}/{total_cells}\n({population_percentage:.1f}%)")

        self.view.population_value.config(text=population_value)

    def main(self) -> None:
        """Start the main application loop."""
        self.view.main()


if __name__ == "__main__":
    game_of_life = Controller()
    game_of_life.main()
