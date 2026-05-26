import csv
import random

from src.printer import get_printer


def load_student_ids(csv_path):
    ids = []
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ids.append(row["student_id"])
    return ids


def main():
    csv_path = "trash/cleaned_combined.csv"
    student_ids = load_student_ids(csv_path)

    print(f"Total IDs available: {len(student_ids)}")
    count = int(input("How many barcodes to print? "))

    if count > len(student_ids):
        print(f"Only {len(student_ids)} IDs available")
        count = len(student_ids)

    selected_ids = random.sample(student_ids, count)

    printer = get_printer()
    if not printer:
        print("No printer found")
        return

    printer._raw(b"\x1b\x40")

    for student_id in selected_ids:
        barcode_value = f"S{student_id}"
        print(f"Printing: {barcode_value}")

        try:
            printer.barcode(
                barcode_value,
                "CODE39",
                width=2,
                height=64,
                pos="BELOW",
                font="A",
            )
            printer.text("\n")
        except Exception as e:
            print(f"Error printing {barcode_value}: {e}")

    printer.text("\n")
    printer.cut()
    print(f"Printed {len(selected_ids)} barcodes")


if __name__ == "__main__":
    main()
