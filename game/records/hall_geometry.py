"""Unveränderte Slot-Geometrie aus der Ruhmeshallen-Vorlage.

Die Werte sind Prozentangaben relativ zum jeweiligen Raumbild. Sie gehören
bewusst in eine kleine, rein visuelle Konstante und werden nicht berechnet:
eine Änderung hier würde die gelieferte Raumvermessung verletzen.
"""

PANEL_SLOT_STYLES = (
    'left:1.61%;top:13.88%;width:16.12%;height:51.47%;--form:polygon(20.3% 0%, 94.3% 7.6%, 99.4% 15.5%, 84.3% 43.6%, 100% 85%, 93.9% 95.7%, 25.2% 100%, 1% 66.2%, 0.9% 62.1%, 0% 27.8%)',
    'left:16.3%;top:18.54%;width:13.8%;height:44.18%;--form:polygon(22.9% 100%, 11.3% 70.4%, 0% 40.8%, 23.3% 0%, 94.7% 4.3%, 100% 12.7%, 83.9% 42.6%, 99.7% 86.2%, 93.6% 97.2%, 90.4% 97.4%)',
    'left:28.98%;top:20.87%;width:13.17%;height:40.51%;--form:polygon(19.9% 100%, 1.8% 47.2%, 0% 41.3%, 22.6% 0%, 94.2% 2%, 100% 10.2%, 84.1% 41.9%, 98.3% 87.3%, 91.6% 98.6%)',
    'left:41.07%;top:21.86%;width:13.13%;height:38.89%;--form:polygon(92.9% 0.2%, 100% 9.7%, 85.1% 42.4%, 98.1% 87.9%, 91.4% 100%, 17.4% 99.9%, 0% 41.7%, 21.7% 0%)',
    'left:53.19%;top:21.32%;width:12.54%;height:39.94%;--form:polygon(93.5% 0%, 100% 8.7%, 84% 42.2%, 96% 87.5%, 88.7% 100%, 17.2% 98.8%, 0% 42.8%, 21.7% 1.7%)',
    'left:64.62%;top:19.41%;width:12.41%;height:42.84%;--form:polygon(23% 4.3%, 92% 0%, 100% 11.2%, 83.6% 43.3%, 92.4% 86.5%, 83.5% 100%, 15.8% 97.9%, 0% 44.1%)',
    'left:75.8%;top:16.93%;width:11.53%;height:47.23%;--form:polygon(90.3% 93.3%, 85.7% 100%, 13.3% 96.5%, 0% 44.4%, 24.8% 4.8%, 91.5% 0%, 93.8% 2%, 100% 10.9%, 94.6% 21%, 82.6% 42.9%, 86% 57%, 90% 71.2%, 94.7% 86.3%)',
    'left:86.09%;top:13.23%;width:12.92%;height:53.5%;--form:polygon(23.6% 5.5%, 75.9% 0%, 100% 27.8%, 99.7% 47.6%, 99.4% 67.9%, 72.3% 100%, 15.1% 95.9%, 10.3% 79.6%, 5.9% 64.8%, 0% 45.2%, 11.7% 25.8%, 20.9% 10.2%)',
)

CLUB_SLOT_STYLES = (
    'left:2.32%;top:22.69%;width:9.85%;height:20.75%;--kipp:-1.47deg;--pado:1.8%;--padu:0.4%;--form:polygon(0% 3.6%, 100% 0%, 99.5% 99.2%, 0.7% 100%)',
    'left:13.47%;top:21.93%;width:10.21%;height:21.29%;--kipp:-1.25deg;--pado:1.8%;--padu:0.1%;--form:polygon(0.1% 3.5%, 99.9% 0%, 100% 99.8%, 0% 100%)',
    'left:25.1%;top:20.99%;width:10.7%;height:22.18%;--kipp:-1.45deg;--pado:2%;--padu:0.2%;--form:polygon(0% 4%, 100% 0%, 99.7% 99.6%, 0.3% 100%)',
    'left:37.34%;top:20.06%;width:10.61%;height:23.04%;--kipp:-1.49deg;--pado:2%;--padu:0.2%;--form:polygon(0% 4%, 100% 0%, 99.7% 99.7%, 0% 100%)',
    'left:49.45%;top:18.9%;width:10.56%;height:24.14%;--kipp:-1.59deg;--pado:2.1%;--padu:0.1%;--form:polygon(0% 4.2%, 99.8% 0%, 100% 99.8%, 0.1% 100%)',
    'left:61.57%;top:17.48%;width:10.82%;height:25.52%;--kipp:-2.18deg;--pado:2.7%;--padu:0.2%;--form:polygon(0% 5.4%, 99.6% 0%, 100% 99.7%, 0% 100%)',
    'left:73.86%;top:15.33%;width:10.78%;height:27.6%;--kipp:-3.07deg;--pado:3.6%;--padu:0.2%;--form:polygon(0.4% 7.1%, 99.9% 0%, 100% 99.6%, 0% 100%)',
    'left:86.2%;top:12.07%;width:10.28%;height:30.8%;--kipp:-4.96deg;--pado:4.9%;--padu:0.3%;--form:polygon(0% 9.8%, 99.9% 0%, 100% 99.4%, 0.3% 100%)',
    'left:2.32%;top:45.37%;width:9.8%;height:19.68%;--kipp:0.85deg;--pado:0.1%;--padu:1.2%;--form:polygon(0% 0%, 100% 0.2%, 100% 100%, 0.7% 97.6%)',
    'left:13.48%;top:45.48%;width:10.18%;height:20.33%;--kipp:0.94deg;--pado:0%;--padu:1.5%;--form:polygon(0.4% 0%, 100% 0%, 100% 100%, 0% 97.1%)',
    'left:25.12%;top:45.47%;width:10.71%;height:21.3%;--kipp:1.22deg;--pado:0%;--padu:1.9%;--form:polygon(0% 0%, 100% 0.1%, 99.9% 100%, 0.2% 96.3%)',
    'left:37.3%;top:45.51%;width:10.62%;height:22.5%;--kipp:1.59deg;--pado:0%;--padu:2.3%;--form:polygon(0% 0%, 99.8% 0%, 100% 100%, 0.6% 95.3%)',
    'left:49.42%;top:45.53%;width:10.6%;height:23.97%;--kipp:2.27deg;--pado:0.3%;--padu:2.9%;--form:polygon(0% 0%, 100% 0.5%, 99.8% 100%, 0.5% 94.3%)',
    'left:61.53%;top:45.72%;width:10.82%;height:25.93%;--kipp:2.87deg;--pado:0.2%;--padu:3.5%;--form:polygon(0% 0%, 100% 0.4%, 99.6% 100%, 0.5% 92.9%)',
    'left:73.84%;top:45.79%;width:10.81%;height:28.9%;--kipp:4.34deg;--pado:0.3%;--padu:4.7%;--form:polygon(0.5% 0%, 99.7% 0.7%, 100% 100%, 0% 90.5%)',
    'left:86.25%;top:46.04%;width:10.24%;height:32.77%;--kipp:5.97deg;--pado:0.3%;--padu:5.5%;--form:polygon(0% 0%, 99.8% 0.7%, 100% 100%, 0.2% 89%)',
)