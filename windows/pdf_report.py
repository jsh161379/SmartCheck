"""SmartCheck PDF reports from persisted SQLite records (no synthetic data)."""
import json
from datetime import date, datetime
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether

NAMES = {'book': '책', 'cell phone': '휴대폰', 'scissors': '가위'}


def _font():
    candidates = [
        Path('C:/Windows/Fonts/malgun.ttf'),
        Path('C:/Windows/Fonts/gulim.ttc'),
        Path('/usr/share/fonts/truetype/nanum/NanumGothic.ttf'),
        Path('/usr/share/fonts/truetype/nanum/NanumSquareR.ttf'),
        Path('/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf'),
    ]
    for path in candidates:
        if path.is_file():
            try:
                pdfmetrics.registerFont(TTFont('SmartCheckKorean', str(path)))
                return 'SmartCheckKorean'
            except Exception:
                continue
    raise RuntimeError('한글 PDF 폰트를 찾지 못했습니다. Windows 맑은 고딕(malgun.ttf)이 필요합니다.')


def _styles():
    font = _font()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='SC_Title', fontName=font, fontSize=17, leading=25, textColor=colors.HexColor('#14283F'), spaceAfter=13))
    styles.add(ParagraphStyle(name='SC_Heading', fontName=font, fontSize=11, leading=17, textColor=colors.HexColor('#22669A'), spaceBefore=12, spaceAfter=7))
    styles.add(ParagraphStyle(name='SC_Body', fontName=font, fontSize=9, leading=15))
    styles.add(ParagraphStyle(name='SC_Small', fontName=font, fontSize=8, leading=12))
    return styles, font


def _p(value, style):
    return Paragraph(escape(str(value if value is not None else '-')).replace('\n', '<br/>'), style)


def _items(raw):
    if not raw:
        return '-'
    parsed = json.loads(raw)
    if isinstance(parsed, list):
        return ', '.join(NAMES.get(x, x) for x in parsed) or '-'
    if isinstance(parsed, dict):
        return ', '.join(f'{NAMES.get(k,k)} {v}/5' for k, v in parsed.items()) or '-'
    return str(parsed)


def _fmt_duration(value):
    return '-' if value is None else f'{value:.1f}초'


def _table(rows, styles, font, widths=None, compact=False):
    table = Table([[_p(v, styles['SC_Small']) for v in row] for row in rows], colWidths=widths, repeatRows=1, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#E8F1F8')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F7FAFD')]),
        ('LINEBELOW', (0,0), (-1,0), 0.8, colors.HexColor('#B7CDE0')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3 if compact else 7),
        ('TOPPADDING', (0,0), (-1,-1), 3 if compact else 7),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    return table


def _build(path, story):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=17*mm, rightMargin=17*mm, topMargin=17*mm, bottomMargin=17*mm,
                            title='SmartCheck Report', author='SmartCheck')
    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#71859A'))
        canvas.drawRightString(A4[0]-17*mm, 11*mm, f'SmartCheck  |  {document.page}')
        canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return path


def _evidence_image(raw_path, styles):
    """Return a PDF-safe, aspect-preserving evidence photo or a clear note."""
    if not raw_path:
        return [_p('증거 이미지: 저장된 파일 경로 없음', styles['SC_Small'])]
    path = Path(raw_path)
    if not path.is_file():
        return [_p('증거 이미지: 파일을 찾을 수 없음 (저장 경로 확인 필요)', styles['SC_Small'])]
    try:
        reader = ImageReader(str(path))
        width, height = reader.getSize()
        if width <= 0 or height <= 0:
            raise ValueError('invalid image dimensions')
        max_width, max_height = 145 * mm, 67 * mm
        scale = min(max_width / width, max_height / height, 1.0)
        image = Image(str(path), width=width * scale, height=height * scale)
        image.hAlign = 'CENTER'
        return [_p('검사 증거 이미지', styles['SC_Small']), Spacer(1, 2*mm), image]
    except Exception:
        return [_p('증거 이미지: 파일을 읽을 수 없음 (형식 또는 파일 상태 확인 필요)', styles['SC_Small'])]


def export_task_report(db, task_id, path):
    """One task plus every inspection/recheck attached to it."""
    task = db.conn.execute('SELECT * FROM tasks WHERE id=?', (task_id,)).fetchone()
    if task is None:
        raise ValueError(f'작업 ID {task_id} 기록이 없습니다.')
    inspections = db.conn.execute('SELECT * FROM inspections WHERE task_id=? ORDER BY id', (task_id,)).fetchall()
    styles, font = _styles()
    story = [_p(f'SmartCheck 개별 작업 보고서  |  #{task_id}', styles['SC_Title']),
             _p(f'보고서 생성: {datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")}', styles['SC_Small']),
             _p('작업 정보', styles['SC_Heading'])]
    data = [
        ('작업 ID', task['id']), ('검사 대상', _items(task['selected_items'])),
        ('작업 상태', task['status']), ('최종 검사 결과', task['last_result'] or '-'),
        ('작업 생성', task['created_at']), ('작업 시작', task['work_started_at'] or '-'),
        ('종료 시각', task['finished_at'] or '-'), ('소요 시간', _fmt_duration(task['duration_seconds'])),
        ('오류 사유', task['error_reason'] or '-'), ('검사 횟수', len(inspections)),
    ]
    story.append(_table([['항목', '저장된 값']] + data, styles, font, [39*mm, 137*mm], compact=True))
    story.append(_p('검사 상세 (재검사 포함)', styles['SC_Heading']))
    if not inspections:
        story.append(_p('저장된 검사 기록이 없습니다.', styles['SC_Body']))
    for row in inspections:
        details = [
            ['검사 ID / 시각', f"#{row['id']}  |  {row['inspected_at']}"],
            ['판정', row['result']],
            ['검사 대상', _items(row['selected_items'])],
            ['누락 물품', _items(row['missing_items'])],
            ['불확실 물품', _items(row['uncertain_items'])],
            ['탐지 횟수', _items(row['detection_counts'])],
            ['신뢰도 / 프레임', f"{row['confidence']:.2f} / {row['total_frames']}"],
            ['증거 이미지 경로', row['evidence_path'] or '-'],
        ]
        # 검사 정보와 증거 사진을 함께 배치하여 사진만 남는 페이지를 방지한다.
        block = [Spacer(1, 2*mm),
                 _table([['항목', '저장된 값']] + details, styles, font,
                        [39*mm, 137*mm], compact=True),
                 Spacer(1, 2*mm)]
        block.extend(_evidence_image(row['evidence_path'], styles))
        story.append(KeepTogether(block))
    return _build(path, story)


def export_period_report(db, start_date, end_date, path):
    """Period inclusive; tasks by created_at, inspections by inspected_at."""
    start = date.fromisoformat(str(start_date))
    end = date.fromisoformat(str(end_date))
    if start > end:
        raise ValueError('시작 날짜가 종료 날짜보다 늦습니다.')
    tasks = db.conn.execute('SELECT * FROM tasks WHERE substr(created_at,1,10) BETWEEN ? AND ? ORDER BY id', (start.isoformat(), end.isoformat())).fetchall()
    inspections = db.conn.execute('SELECT * FROM inspections WHERE substr(inspected_at,1,10) BETWEEN ? AND ? ORDER BY id', (start.isoformat(), end.isoformat())).fetchall()
    states = {}
    results = {}
    missing = {x: 0 for x in NAMES}
    uncertain = {x: 0 for x in NAMES}
    durations = []
    for row in tasks:
        states[row['status']] = states.get(row['status'], 0) + 1
        if row['status'] == 'COMPLETED' and row['duration_seconds'] is not None:
            durations.append(row['duration_seconds'])
    for row in inspections:
        results[row['result']] = results.get(row['result'], 0) + 1
        for x in json.loads(row['missing_items']):
            missing[x] = missing.get(x, 0) + 1
        for x in json.loads(row['uncertain_items']):
            uncertain[x] = uncertain.get(x, 0) + 1
    styles, font = _styles()
    story = [_p('SmartCheck 기간별 요약 보고서', styles['SC_Title']),
             _p(f'조회 기간: {start} ~ {end} (양끝 날짜 포함)', styles['SC_Body']),
             _p('집계 기준: 작업은 생성일, 검사는 검사일 기준으로 각각 조회합니다. 날짜 경계를 넘는 작업은 두 집계에 다르게 반영될 수 있습니다.', styles['SC_Small']),
             _p(f'보고서 생성: {datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")}', styles['SC_Small']),
             _p('검사·작업 집계', styles['SC_Heading'])]
    summary = [
        ('전체 작업', len(tasks)), ('전체 검사', len(inspections)),
        ('PASS', results.get('PASS', 0)), ('FAIL', results.get('FAIL', 0)), ('RECHECK', results.get('RECHECK', 0)),
        ('작업 완료', states.get('COMPLETED', 0)), ('작업 취소', states.get('CANCELED', 0)),
        ('비정상 종료', states.get('INTERRUPTED', 0)), ('오류', states.get('ERROR', 0)),
    ]
    story.append(_table([['항목', '건수']] + summary, styles, font, [88*mm, 88*mm]))
    story.append(_p('물품별 누락·불확실 횟수', styles['SC_Heading']))
    story.append(_table([['물품', '누락', '불확실']] + [[name, missing.get(k,0), uncertain.get(k,0)] for k,name in NAMES.items()], styles, font, [58*mm]*3))
    story.append(_p('완료 작업 소요 시간', styles['SC_Heading']))
    duration_text = (f'{len(durations)}건  |  평균 {sum(durations)/len(durations):.1f}초  |  최소 {min(durations):.1f}초  |  최대 {max(durations):.1f}초') if durations else '완료 작업 기록 없음'
    story.append(_p(duration_text, styles['SC_Body']))
    story.append(_p('기간 내 작업 목록 (생성일 기준)', styles['SC_Heading']))
    if tasks:
        rows = [['작업 ID', '생성 시각', '상태', '검사 결과', '소요 시간']]
        rows.extend([f"#{r['id']}", r['created_at'][:19].replace('T',' '), r['status'], r['last_result'] or '-', _fmt_duration(r['duration_seconds'])] for r in tasks)
        story.append(_table(rows, styles, font, [19*mm, 62*mm, 34*mm, 30*mm, 31*mm]))
    else:
        story.append(_p('해당 기간에 저장된 작업이 없습니다.', styles['SC_Body']))
    story.append(Spacer(1, 6*mm))
    story.append(_p('※ 작업 건수는 생성일 기준, 검사 건수는 검사일 기준으로 각각 집계합니다.', styles['SC_Small']))
    return _build(path, story)
