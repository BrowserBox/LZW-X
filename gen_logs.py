import random

def generate_logs(filename, count=20000):
    users = [f"user_{i}" for i in range(50)]
    ips = [f"192.168.1.{i}" for i in range(255)]
    actions = ["logged_in", "logged_out", "failed_auth", "viewed_page_index", "viewed_page_profile"]
    
    with open(filename, 'w') as f:
        for i in range(count):
            ts = f"2026-01-29 12:{i%60:02d}:{i%60:02d}"
            user = random.choice(users)
            ip = random.choice(ips)
            action = random.choice(actions)
            line = f"{ts} INFO [AuthService] {user} {action} from {ip}\n"
            f.write(line)

if __name__ == "__main__":
    generate_logs("synthetic.log")
