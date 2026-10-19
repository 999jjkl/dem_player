import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess

# ==========================================
# --- PATH TO YOUR EXECUTABLE ---
# ==========================================
# If furnace.exe is in your system PATH, you can just leave this as "furnace".
# Otherwise, replace it with the exact path to your executable file.
FURNACE_PATH = "furnace.exe" 

def browse_input():
    # FIXED: Now properly searches for BOTH .dnm and .ftm files!
    file_path = filedialog.askopenfilename(
        filetypes=[
            ("Chiptune Files (*.dnm, *.ftm)", "*.dnm *.ftm"),
            ("Dn-FamiTracker Files (*.dnm)", "*.dnm"),
            ("FamiTracker Files (*.ftm)", "*.ftm")
        ]
    )
    if file_path:
        input_entry.delete(0, tk.END)
        input_entry.insert(0, file_path)

def browse_output():
    file_path = filedialog.asksaveasfilename(
        defaultextension=".wav", 
        filetypes=[("WAV Audio", "*.wav")]
    )
    if file_path:
        output_entry.delete(0, tk.END)
        output_entry.insert(0, file_path)

def convert_file():
    input_file = input_entry.get()
    output_wav = output_entry.get()
    
    if not input_file or not output_wav:
        messagebox.showerror("Error", "Please select both an input file and an output destination.")
        return
    
    status_label.config(text="Status: Exporting module to WAV...", fg="blue")
    root.update()

    try:
        # Run Furnace to export either the .dnm or .ftm file directly to WAV
        furnace_cmd = [FURNACE_PATH, "-output", output_wav, input_file]
        subprocess.run(furnace_cmd, check=True, creationflags=subprocess.CREATE_NO_WINDOW)

        status_label.config(text="Status: Conversion Successful!", fg="green")
        messagebox.showinfo("Success", "WAV file created successfully!")
        
    except FileNotFoundError:
        status_label.config(text="Status: Error - Tool not found.", fg="red")
        messagebox.showerror("Error", "Could not find 'furnace.exe'. Make sure it is in the same folder or added to your system PATH.")
    except Exception as e:
        status_label.config(text="Status: Error occurred.", fg="red")
        messagebox.showerror("Error", f"An error occurred during conversion:\n{str(e)}")

# ==========================================
# --- GUI LAYOUT SETUP ---
# ==========================================
root = tk.Tk()
root.title("Chiptune to WAV Converter (DNM & FTM)")
root.geometry("500x250")
root.resizable(False, False)

# Input File GUI Elements
tk.Label(root, text="Source Tracker File (.DNM or .FTM):", font=("Arial", 10, "bold")).pack(anchor="w", padx=15, pady=(15, 2))
input_frame = tk.Frame(root)
input_frame.pack(fill="x", padx=15)
input_entry = tk.Entry(input_frame, width=50)
input_entry.pack(side="left", expand=True, fill="x")
tk.Button(input_frame, text="Browse...", command=browse_input).pack(side="right", padx=5)

# Output File GUI Elements
tk.Label(root, text="Save WAV Destination:", font=("Arial", 10, "bold")).pack(anchor="w", padx=15, pady=(15, 2))
output_frame = tk.Frame(root)
output_frame.pack(fill="x", padx=15)
output_entry = tk.Entry(output_frame, width=50)
output_entry.pack(side="left", expand=True, fill="x")
tk.Button(output_frame, text="Browse...", command=browse_output).pack(side="right", padx=5)

# Dynamic Status text
status_label = tk.Label(root, text="Status: Idle", font=("Arial", 10, "italic"))
status_label.pack(pady=15)

# Action Trigger Button
convert_btn = tk.Button(root, text="Convert to WAV", font=("Arial", 12, "bold"), bg="#4CAF50", fg="white", command=convert_file, padx=10, pady=5)
convert_btn.pack(pady=5)

root.mainloop()