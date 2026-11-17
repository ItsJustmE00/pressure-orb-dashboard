import urllib.request

token = "8771213601:AAHLSo8DrRSbc_yIljSGS0UgVbmAlKPzxNE"
chat_id = "6920893630"
path = r"out_orb_manage\1_equity_curves.png"

boundary = "----ORBxBoundary9"
body = (
    f"--{boundary}\r\n"
    'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
    f"{chat_id}\r\n"
    f"--{boundary}\r\n"
    'Content-Disposition: form-data; name="caption"\r\n\r\n'
    "Equite ORB BOTH 0,5% : 2R max2 (cyan) > 3R max1 (violet) > 1R (jaune). "
    "OOS 2022-2026, donnees reelles. Config live confirmee : 2R, max 2/jour.\r\n"
    f"--{boundary}\r\n"
    'Content-Disposition: form-data; name="photo"; '
    f'filename="1_equity_curves.png"\r\n'
    "Content-Type: image/png\r\n\r\n"
).encode() + open(path, "rb").read() + f"\r\n--{boundary}--\r\n".encode()

req = urllib.request.Request(
    f"https://api.telegram.org/bot{token}/sendPhoto",
    data=body,
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
)
with urllib.request.urlopen(req, timeout=60) as r:
    print("photo envoyee", r.status)
