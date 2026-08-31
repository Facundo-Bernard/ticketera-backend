from datetime import datetime, date, time, timezone
from typing import Optional, Union
import re

def parse_date_filter(
    date_val: Optional[Union[str, datetime, date]], 
    is_end_date: bool = False
) -> Optional[datetime]:
    """
    Parsea fechas para filtros de tickets.
    - fecha_desde: autocompleta automáticamente a las 00:00:00.000000 UTC del día.
    - fecha_hasta: autocompleta automáticamente a las 23:59:59.999999 UTC del día.
    Soporta formatos YYYY-MM-DD, ISO (con o sin hora), DD/MM/YYYY, etc.
    """
    if date_val is None:
        return None
        
    extracted_date: Optional[date] = None

    if isinstance(date_val, datetime):
        extracted_date = date_val.date()
    elif isinstance(date_val, date):
        extracted_date = date_val
    elif isinstance(date_val, str):
        val = date_val.strip()
        if not val or val.lower() in ("null", "none", "undefined"):
            return None

        # 1. Intentar ISO directo
        try:
            clean_val = val.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_val)
            extracted_date = dt.date()
        except ValueError:
            pass

        # 2. Formato YYYY-MM-DD o YYYY/MM/DD
        if not extracted_date:
            match_ymd = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})", val)
            if match_ymd:
                y, m, d = map(int, match_ymd.groups())
                try:
                    extracted_date = date(y, m, d)
                except ValueError:
                    pass

        # 3. Formato DD-MM-YYYY o DD/MM/YYYY
        if not extracted_date:
            match_dmy = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})", val)
            if match_dmy:
                d, m, y = map(int, match_dmy.groups())
                try:
                    extracted_date = date(y, m, d)
                except ValueError:
                    pass

        # 4. Formatos con hora y espacio
        if not extracted_date:
            for fmt in (
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y/%m/%d %H:%M:%S",
                "%Y/%m/%d %H:%M",
                "%d/%m/%Y %H:%M:%S",
                "%d/%m/%Y %H:%M",
                "%d-%m-%Y %H:%M:%S",
                "%d-%m-%Y %H:%M"
            ):
                try:
                    dt = datetime.strptime(val, fmt)
                    extracted_date = dt.date()
                    break
                except ValueError:
                    continue

    if extracted_date is None:
        return None

    # Autocompletar la hora según sea fecha_desde o fecha_hasta
    if is_end_date:
        return datetime.combine(extracted_date, time(23, 59, 59, 999999, tzinfo=timezone.utc))
    else:
        return datetime.combine(extracted_date, time(0, 0, 0, 0, tzinfo=timezone.utc))

