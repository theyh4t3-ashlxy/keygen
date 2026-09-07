import itertools

# Using the longer 6-word phrase
sentence = "your text here"
words = sentence.lower().split()

# set() automatically filters out any duplicate sentence structures
unique_permutations = set(itertools.permutations(words))

print(f"Total unique permutations: {len(unique_permutations)}")
print("First 5 examples:")
for p in list(unique_permutations)[:720]:
    print(" ".join(p))
