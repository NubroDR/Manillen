#ManillenGUI
import time
import ipywidgets as widgets
from IPython.display import display, clear_output

import tkinter as tk
from tkinter import ttk


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


def create_player_selector_widget(all_players):
    """Create an IPython widget selector for active players."""
    all_players = sorted(all_players)
    selected = []  # default: all players available, none selected

    filter_text = widgets.Text(
        description='Filter:',
        placeholder='Type to search players...',
        layout=widgets.Layout(width='100%')
    )

    available_list = widgets.SelectMultiple(
        options=tuple(p for p in all_players if p not in selected),
        rows=18,
        description='Available',
        layout=widgets.Layout(width='38%')
    )

    selected_list = widgets.SelectMultiple(
        options=tuple(selected),
        rows=18,
        description='Selected',
        layout=widgets.Layout(width='38%')
    )

    add_btn = widgets.Button(description='Add ->', button_style='success', layout=widgets.Layout(width='100%'))
    remove_btn = widgets.Button(description='<- Remove', button_style='warning', layout=widgets.Layout(width='100%'))
    select_all_btn = widgets.Button(description='Select All', button_style='info', layout=widgets.Layout(width='100%'))
    deselect_all_btn = widgets.Button(description='Deselect All', button_style='danger', layout=widgets.Layout(width='100%'))
    confirm_btn = widgets.Button(description='Confirm Selection', button_style='primary', layout=widgets.Layout(width='100%'))
    status = widgets.HTML(value=f'<b>Selected:</b> {len(selected)} / {len(all_players)}')

    selected_players = []

    def update_lists():
        filtered = [p for p in all_players if filter_text.value.lower() in p.lower() and p not in selected]
        available_list.options = tuple(filtered)
        selected_list.options = tuple(selected)
        available_list.value = ()
        selected_list.value = ()
        status.value = f'<b>Selected:</b> {len(selected)} / {len(all_players)}'

    def add_selected(_=None):
        for player in available_list.value:
            if player not in selected:
                selected.append(player)
        selected.sort()
        update_lists()

    def remove_selected(_=None):
        for player in selected_list.value:
            if player in selected:
                selected.remove(player)
        update_lists()

    def select_all(_=None):
        selected[:] = all_players[:]
        selected.sort()
        update_lists()

    def deselect_all(_=None):
        selected.clear()
        update_lists()

    def on_filter_change(change):
        update_lists()

    def confirm(_=None):
        selected_players.clear()
        selected_players.extend(selected)
        status.value = '<b>Selection confirmed.</b>'
        add_btn.disabled = True
        remove_btn.disabled = True
        select_all_btn.disabled = True
        deselect_all_btn.disabled = True
        filter_text.disabled = True

    filter_text.observe(on_filter_change, names='value')
    add_btn.on_click(add_selected)
    remove_btn.on_click(remove_selected)
    select_all_btn.on_click(select_all)
    deselect_all_btn.on_click(deselect_all)
    confirm_btn.on_click(confirm)

    move_box = widgets.VBox(
        [add_btn, remove_btn, select_all_btn, deselect_all_btn],
        layout=widgets.Layout(width='20%', min_width='120px')
    )
    lists_box = widgets.HBox(
        [available_list, move_box, selected_list],
        layout=widgets.Layout(align_items='center', width='100%')
    )
    main_box = widgets.VBox(
        [filter_text, lists_box, status, confirm_btn],
        layout=widgets.Layout(width='100%', min_height='300px')
    )

    display(main_box)

    return selected_players


# Usage example:
# AllPlayers = ["Marc", "Peter", "Freddy", "Zoë", ...]
# ActivePlayers = create_player_selector_window(AllPlayers)
# print(f"Selected: {ActivePlayers}")
# ActivePlayers = create_player_selector_widget(AllPlayers)
# print(f"Selected: {ActivePlayers}")