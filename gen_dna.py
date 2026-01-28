import random

def generate_dna(filename, size_mb=1):
    bases = ['A', 'C', 'G', 'T']
    genes = []
    for _ in range(20):
        gene = "".join(random.choice(bases) for _ in range(500))
        genes.append(gene)
    
    target_size = size_mb * 1024 * 1024
    current_size = 0
    
    with open(filename, 'w') as f:
        while current_size < target_size:
            gene = random.choice(genes)
            mutated = list(gene)
            if random.random() < 0.5:
                num_mutations = random.choice([1, 2])
                for _ in range(num_mutations):
                    op = random.choices(['sub', 'ins', 'del', 'trans'], weights=[0.1, 0.4, 0.4, 0.1])[0]
                    pos = random.randint(0, len(mutated) - 2)
                    if op == 'sub': mutated[pos] = random.choice(bases)
                    elif op == 'ins': mutated.insert(pos, random.choice(bases))
                    elif op == 'del': 
                        if len(mutated) > 1: del mutated[pos]
                    elif op == 'trans': mutated[pos], mutated[pos+1] = mutated[pos+1], mutated[pos]
            segment = "".join(mutated)
            f.write(segment)
            current_size += len(segment)

if __name__ == "__main__":
    generate_dna("synthetic_dna.txt")
