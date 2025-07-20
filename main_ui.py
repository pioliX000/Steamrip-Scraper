from rapidfuzz import fuzz
import json
from bs4 import BeautifulSoup
import requests
import re
import tkinter as tk
from tkinter import ttk
import threading
import queue
import webbrowser # Import the webbrowser module
import os
import urllib.request
import concurrent.futures

TRUSTED = ["drive.google.com", "megaup.net", "mega.nz", "urlbluemedia"]
TRUSTED_SECTIONS = ["Link MegaUp.net", "Link Mega.nz", "Link Mega.co.nz", "Link Google Drive"]

if not os.path.exists(os.path.expandvars(r"%USERPROFILE%\\Documents\\Steamrip-Scraper")):
	os.mkdir(os.path.expandvars(r"%USERPROFILE%\\Documents\\Steamrip-Scraper"))
	urllib.request.urlretrieve("https://raw.githubusercontent.com/pioliX000/Steamrip-Scraper/refs/heads/main/links_reformatted.json", os.path.expandvars(r"%USERPROFILE%\\Documents\\Steamrip-Scraper\\links_reformatted.json"))

def deobfuscate(url):
	try:
		html = requests.get(url, timeout=10).text
		matches = re.search(r"_0x44b739='.*?'", html)

		if matches:
			obfuscated = matches.group(0)[11:-1]
			half = len(obfuscated) // 2
			part1 = ''.join(obfuscated[i] for i in range(half - 5, -1, -2))
			part2 = ''.join(obfuscated[i] for i in range(half + 4, len(obfuscated), 2))
			token = part1 + part2
			intermediate_url = f"https://urlbluemedia.shop/get-url.php?url={token}"
			response = requests.get(intermediate_url, allow_redirects=True, timeout=10)
			return response.url
		else:
			return None
	except requests.exceptions.RequestException as e:
		return None
	except Exception as e:
		return None

def part_number(link):
	try:
		part_str = link.split('.part')[1].split('.rar')[0]
		return int(part_str)
	except (IndexError, ValueError):
		return float('inf')

def extract_links(url):
	download_links = []
	links_to_deobfuscate = []

	try:
		response = requests.get(url, timeout=10)
		soup = BeautifulSoup(response.content, 'html.parser')
		categorized_links = {}

		for tag in soup.find_all('a', string="DOWNLOAD HERE"):
			links = []
			links.append(tag['href'])

		categorized_links["temp"] = links

		for section, urls in categorized_links.items():
			# if not section in TRUSTED_SECTIONS:
			# 	continue
			for href in urls:
				if 'urlbluemedia' in href:
					links_to_deobfuscate.append(href)
				else:
					download_links.append("https:" + href)

		# with concurrent.futures.ThreadPoolExecutor(max_workers=len(links_to_deobfuscate)) as executor:
		# 	future_to_link = {executor.submit(deobfuscate, link): link for link in links_to_deobfuscate}

		# 	for future in concurrent.futures.as_completed(future_to_link):
		# 		original_link = future_to_link[future]
		# 		deobf_link = future.result()
		# 		if deobf_link:
		# 			if any(trusted_url in deobf_link for trusted_url in TRUSTED):
		# 				download_links.append(deobf_link)
		
		# download_links = sorted(download_links, key=part_number)
		return download_links
	except requests.exceptions.RequestException as e:
		return []
	except Exception as e:
		# print(e)
		return []

class ThreadedLinkExtractor(threading.Thread):
	def __init__(self, game_url, result_queue):
		threading.Thread.__init__(self)
		self.game_url = game_url
		self.result_queue = result_queue

	def run(self):
		links = extract_links(self.game_url)
		self.result_queue.put(links)

class GameSelectorApp:
	def __init__(self, root, games_data):
		self.root = root
		self.root.title("Game Downloader")
		self.all_games_data = games_data
		self.filtered_games_data = list(games_data)
		self.current_game_index = 0
		self.games_per_page = 10

		self.link_extraction_queue = queue.Queue()

		self.search_frame = tk.Frame(root)
		self.search_frame.pack(fill="x", padx=10, pady=5)

		self.search_label = tk.Label(self.search_frame, text="Search Game:")
		self.search_label.pack(side="left", padx=(0, 5))

		self.search_entry = tk.Entry(self.search_frame, width=50)
		self.search_entry.pack(side="left", expand=True, fill="x")
		self.search_entry.bind("<KeyRelease>", self.on_search_change)

		self.search_button = tk.Button(self.search_frame, text="Search", command=self.perform_search)
		self.search_button.pack(side="left", padx=(5, 0))

		self.update_button = tk.Button(self.search_frame, text="Update Repo", command=self.update_repo)
		self.update_button.pack(side="left", padx=(5, 0))

		self.game_list_frame = tk.Frame(root)
		self.game_list_frame.pack(fill="both", expand=True, padx=10, pady=10)

		self.canvas = tk.Canvas(self.game_list_frame, borderwidth=0)
		self.game_scroll_frame = tk.Frame(self.canvas)
		self.vsb = ttk.Scrollbar(self.game_list_frame, orient="vertical", command=self.canvas.yview)
		self.canvas.configure(yscrollcommand=self.vsb.set)

		self.vsb.pack(side="right", fill="y")
		self.canvas.pack(side="left", fill="both", expand=True)
		self.canvas.create_window((0, 0), window=self.game_scroll_frame, anchor="nw",
								  tags="self.game_scroll_frame")

		self.game_scroll_frame.bind("<Configure>", self.on_frame_configure)
		self.canvas.bind('<Enter>', self.bind_mouse_wheel)
		self.canvas.bind('<Leave>', self.unbind_mouse_wheel)

		self.display_games(self.filtered_games_data)

		self.download_links_frame = tk.Frame(root)
		self.download_links_label = tk.Label(self.download_links_frame, text="Download Links:", font=("Arial", 12, "bold"))
		self.download_links_label.pack(pady=5)
		self.links_text_area = tk.Text(self.download_links_frame, height=15, width=80, wrap="word")
		self.links_text_area.pack(pady=5)
		self.links_text_area.config(state=tk.DISABLED)

		self.links_text_area.tag_configure("link", foreground="blue", underline=True)

		self.links_text_area.tag_bind("link", "<Button-1>", self.on_link_click)

		self.links_text_area.tag_bind("link", "<Enter>", self.on_link_enter)
		self.links_text_area.tag_bind("link", "<Leave>", self.on_link_leave)


		self.back_button = tk.Button(self.download_links_frame, text="Back to Games", command=self.show_game_list)
		self.back_button.pack(pady=10)

		self.loading_label = tk.Label(self.download_links_frame, text="Fetching links... Please wait.", font=("Arial", 10, "italic"), fg="blue")

	def on_frame_configure(self, event):
		self.canvas.configure(scrollregion=self.canvas.bbox("all"))

	def bind_mouse_wheel(self, event):
		self.canvas.bind_all("<MouseWheel>", self._on_mouse_wheel)

	def unbind_mouse_wheel(self, event):
		self.canvas.unbind_all("<MouseWheel>")

	def _on_mouse_wheel(self, event):
		self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

	def perform_search(self):
		search_query = self.search_entry.get().lower()
		self.filtered_games_data = []
		for game in self.all_games_data:
			game_name = game["name"].lower()

			score = fuzz.token_set_ratio(search_query, game_name)

			if score >= 70:
				self.filtered_games_data.append(game)

		self.current_game_index = 0
		self.display_games(self.filtered_games_data)

	def update_repo(self):
		urllib.request.urlretrieve("https://raw.githubusercontent.com/pioliX000/IGG-Scraper/refs/heads/main/links_reformatted.json", os.path.expandvars(r"%USERPROFILE%\\Documents\\IGG-Scraper\\links_reformatted.json"))
		t = tk.Toplevel(self.root)
		t.wm_title("Info")
		l = tk.Label(t, text="Repo Update Successful\nrestart to apply")
		l.pack(side="top", fill="both", expand=True, padx=50, pady=10)
		
	def on_search_change(self, event):
		self.perform_search()

	def show_download_links(self, game):
		self.search_frame.pack_forget()
		self.game_list_frame.pack_forget()
		self.download_links_frame.pack(fill="both", expand=True, padx=10, pady=10)

		self.links_text_area.config(state=tk.NORMAL)
		self.links_text_area.delete("1.0", tk.END)
		self.links_text_area.insert(tk.END, f"Selected: {game['name']}\n")
		self.links_text_area.config(state=tk.DISABLED)

		self.loading_label.pack(pady=5)

		self.current_game_name = game["name"]
		thread = ThreadedLinkExtractor(game["url"], self.link_extraction_queue)
		thread.start()

		self.root.after(100, self.process_queue)

	def process_queue(self):
		try:
			download_links = self.link_extraction_queue.get(0)
			self.display_download_links_results(download_links)
			self.loading_label.pack_forget()
		except queue.Empty:
			self.root.after(100, self.process_queue)

	def display_download_links_results(self, download_links):
		self.links_text_area.config(state=tk.NORMAL)
		self.links_text_area.delete("1.0", tk.END)

		self.links_text_area.insert(tk.END, f"Download Links for: {self.current_game_name}\n\n")

		if download_links:
			self.links_text_area.insert(tk.END, f"Nur Links von der selben Domain benutzen!\n\n")

			for link in download_links:
				self.links_text_area.insert(tk.END, f"{link}\n", "link")
		else:
			self.links_text_area.insert(tk.END, "No download links found or an error occurred.\n")
		self.links_text_area.config(state=tk.DISABLED)

	def on_link_click(self, event):
		index = self.links_text_area.index(f"@{event.x},{event.y}")

		tags = self.links_text_area.tag_names(index)

		if "link" in tags:
			line_start = self.links_text_area.index(f"{index} linestart")
			line_end = self.links_text_area.index(f"{index} lineend")
			clicked_url = self.links_text_area.get(line_start, line_end).strip()

			if clicked_url.startswith("http://") or clicked_url.startswith("https://"):
				self.open_url(clicked_url)
			else:
				print(f"Clicked text '{clicked_url}' is not a recognized URL.")

	def on_link_enter(self, event):
		self.links_text_area.config(cursor="hand2")

	def on_link_leave(self, event):
		self.links_text_area.config(cursor="") 

	def open_url(self, url):
		try:
			webbrowser.open_new_tab(url)
		except Exception as e:
			print(f"Failed to open URL {url}: {e}")


	def display_games(self, games_to_display):
		for widget in self.game_scroll_frame.winfo_children():
			widget.destroy()

		start_index = self.current_game_index
		end_index = min(self.current_game_index + self.games_per_page, len(games_to_display))

		if not games_to_display:
			tk.Label(self.game_scroll_frame, text="No games found matching your search.", fg="red").pack(pady=20)
			self.canvas.update_idletasks()
			self.on_frame_configure(None)
			return

		for i in range(start_index, end_index):
			game = games_to_display[i]
			game_button = tk.Button(self.game_scroll_frame,
									text=game["name"],
									command=lambda g=game: self.show_download_links(g),
									font=("Arial", 10),
									wraplength=350,
									justify="left")
			game_button.pack(fill="x", padx=5, pady=2)

		if end_index < len(games_to_display):
			load_more_button = tk.Button(self.game_scroll_frame, text="Load More Games", command=self.load_more_games)
			load_more_button.pack(pady=10)
		
		self.canvas.update_idletasks()
		self.on_frame_configure(None)

	def load_more_games(self):
		self.current_game_index += self.games_per_page
		self.display_games(self.filtered_games_data)

	def show_game_list(self):
		self.download_links_frame.pack_forget()
		self.search_frame.pack(fill="x", padx=10, pady=5)
		self.game_list_frame.pack(fill="both", expand=True, padx=10, pady=10)
		self.display_games(self.filtered_games_data)

if __name__ == "__main__":
	try:
		with open(os.path.expandvars(r"%USERPROFILE%\\Documents\\Steamrip-Scraper\\links_reformatted.json"), "r", encoding="utf8") as json_file:
			game_links = json.load(json_file)
	except FileNotFoundError:
		print("links_reformatted.json not found. Please create it with your game data.")
		game_links = []
	except json.JSONDecodeError:
		print("Error decoding links_reformatted.json. Please check its format.")
		game_links = []

	root = tk.Tk()
	app = GameSelectorApp(root, game_links)
	root.mainloop()