from libs.BrtotherDriver import BrotherDriver

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
printer = BrotherDriver()
print(printer.get_status())
label = {"label": "22-0000001", "data": "22-0000001", "company": "XXXXX"}
labelbc = {"label": "50052220", "data": "50052220", "company": "XXXXX"}
#printer.push_task("barcode", label)
printer.push_task("qrcode", label)
