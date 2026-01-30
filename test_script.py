from escpos.printer import Usb

VENDOR_ID = ""
PRODUCT_ID = ""

try:
    p = Usb(VENDOR_ID, PRODUCT_ID, 0, profile="TM-T88III")

    p.set(align="center", bold=True)

    p.text("\n")
    p.text("********************************\n")
    p.text("    SYSTEM ONLINE: ADHD MODE    \n")
    p.text("********************************\n")
    p.text("\n")

    p.set(align="left", bold=False)
    p.text("Current Objective:\n")
    p.text("- Setup Receipt Printer [x]\n")
    p.text("- Connect to Todoist    [x]\n")
    p.text("\n")
    p.text("\n")

    p.cut()

    print("Success! Printer should be buzzing")

except Exception as e:
    print(f"Error: {e}")
    print("Tip: Did you update the Vendor/Product IDs in the script?")
