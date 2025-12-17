#ManillenGUI
import ipywidgets as widgets
from IPython.display import display

import tkinter as tk
from tkinter import ttk

def create_player_selector(all_players):
    """
    Create an interactive GUI for selecting active players.
    Returns a widget that you can use to get selected players.
    """
    # Create checkboxes for each player (all checked by default)
    checkboxes = [
        widgets.Checkbox(value=True, description=player, indent=False)
        for player in all_players
    ]
    
    # Select All / Deselect All buttons
    select_all_btn = widgets.Button(description="Select All", button_style='success')
    deselect_all_btn = widgets.Button(description="Deselect All", button_style='warning')
    
    def select_all(b):
        for cb in checkboxes:
            cb.value = True
    
    def deselect_all(b):
        for cb in checkboxes:
            cb.value = False
    
    select_all_btn.on_click(select_all)
    deselect_all_btn.on_click(deselect_all)
    
    # Layout
    buttons = widgets.HBox([select_all_btn, deselect_all_btn])
    checkbox_container = widgets.VBox(checkboxes)
    
    # Count display
    count_label = widgets.Label(value=f"Selected: {len(all_players)} players")
    
    def update_count(*args):
        selected = sum(1 for cb in checkboxes if cb.value)
        count_label.value = f"Selected: {selected} players"
    
    for cb in checkboxes:
        cb.observe(update_count, 'value')
    
    # Complete interface
    interface = widgets.VBox([
        widgets.HTML("<h3>Select Active Players</h3>"),
        buttons,
        count_label,
        checkbox_container
    ])
    
    # Function to get selected players
    def get_selected_players():
        return [cb.description for cb in checkboxes if cb.value]
    
    interface.get_selected_players = get_selected_players
    
    return interface


# Usage example:
# AllPlayers = ["Marc", "Peter", "Freddy", "Zoë", ...]
# selector = create_player_selector(AllPlayers)
# display(selector)
# 
# # Later, get the selected players:
# ActivePlayers = selector.get_selected_players()


def create_player_selector_window(all_players):
    """
    Create a Tkinter window for selecting active players.
    Returns the list of selected players when window is closed.
    """
    selected_players = []
    
    # Create main window
    root = tk.Tk()
    root.title("Select Active Players")
    root.geometry("400x850")
    root.resizable(True, True)
    
    # Title
    title_label = tk.Label(root, text="Select Active Players", font=("Arial", 14, "bold"))
    title_label.pack(pady=10)
    
    # Buttons frame
    button_frame = tk.Frame(root)
    button_frame.pack(pady=5)
    
    # Count label
    count_label = tk.Label(root, text=f"Selected: {len(all_players)} players", font=("Arial", 10))
    count_label.pack(pady=5)
    
    # Scrollable frame for checkboxes
    checkbox_frame = tk.Frame(root)
    checkbox_frame.pack(fill="both", expand=True, padx=10, pady=5)
    
    canvas = tk.Canvas(checkbox_frame)
    scrollbar = ttk.Scrollbar(checkbox_frame, orient="vertical", command=canvas.yview)
    scrollable_frame = tk.Frame(canvas)
    
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    
    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    # Create checkboxes
    checkbox_vars = []
    checkboxes = []
    
    for player in all_players:
        var = tk.BooleanVar(value=True)
        checkbox_vars.append(var)
        
        cb = tk.Checkbutton(
            scrollable_frame, 
            text=player, 
            variable=var,
            font=("Arial", 10),
            anchor="w",
            command=lambda: update_count()
        )
        cb.pack(fill="x", padx=20, pady=2)
        checkboxes.append(cb)
    
    def update_count():
        selected = sum(1 for var in checkbox_vars if var.get())
        count_label.config(text=f"Selected: {selected} players")
    
    def select_all():
        for var in checkbox_vars:
            var.set(True)
        update_count()
    
    def deselect_all():
        for var in checkbox_vars:
            var.set(False)
        update_count()
    
    def confirm_selection():
        nonlocal selected_players
        selected_players = [
            all_players[i] for i, var in enumerate(checkbox_vars) if var.get()
        ]
        root.quit()
        root.destroy()
    
    # Buttons
    select_all_btn = tk.Button(button_frame, text="Select All", command=select_all, bg="#90EE90")
    select_all_btn.pack(side="left", padx=5)
    
    deselect_all_btn = tk.Button(button_frame, text="Deselect All", command=deselect_all, bg="#FFB6C1")
    deselect_all_btn.pack(side="left", padx=5)
    
    # Pack canvas and scrollbar inside checkbox_frame
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
    # Confirm button at bottom
    confirm_btn = tk.Button(
        root, 
        text="Confirm Selection", 
        command=confirm_selection,
        bg="#4CAF50",
        fg="white",
        font=("Arial", 12, "bold"),
        pady=10
    )
    confirm_btn.pack(pady=10, padx=20, fill="x")
    
    # Start GUI
    root.mainloop()
    
    return selected_players


# Usage example:
# AllPlayers = ["Marc", "Peter", "Freddy", "Zoë", ...]
# ActivePlayers = create_player_selector_window(AllPlayers)
# print(f"Selected: {ActivePlayers}")