import asyncio, logging, os, re
from datetime import datetime
from pathlib import Path
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from storage import Store
from contracts import create_contract

load_dotenv()
TOKEN=os.getenv('BOT_TOKEN','').strip(); MANAGER_ID=int(os.getenv('MANAGER_ID','512322547'))
COMPANY_PHONE=os.getenv('COMPANY_PHONE','+380 67 009 13 88')
if not TOKEN: raise RuntimeError('Заповніть BOT_TOKEN у файлі .env')
logging.basicConfig(level=logging.INFO)
bot=Bot(TOKEN); dp=Dispatcher(storage=MemoryStorage()); db=Store('data/bot.sqlite3')
SERVICES=['Повірка водоміра','Повірка теплолічильника','Встановлення водоміра','Встановлення теплолічильника','Ремонт приладу обліку','Консультація']
DEVICES=['Водомір','Теплолічильник']
class Intake(StatesGroup):
    name=State(); phone=State(); service=State(); device=State(); address=State(); quantity=State(); details=State(); confirm=State()

@dp.message(CommandStart())
async def start(m:Message,state:FSMContext):
    await state.clear()
    kb=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='Подати заявку')]],resize_keyboard=True)
    await m.answer('Вітаємо! Ви звернулися до ТОВ «УКРМЕТРОЛОГІЯ».\n\nЩоб оформити заявку, натисніть кнопку нижче.',reply_markup=kb)

@dp.message(Command('cancel'))
async def cancel(m:Message,state:FSMContext):
    await state.clear(); await m.answer('Оформлення заявки скасовано. Щоб почати знову, натисніть «Подати заявку».')

@dp.message(F.text=='Подати заявку')
async def begin(m:Message,state:FSMContext):
    await state.clear(); await state.set_state(Intake.name)
    await m.answer('Вкажіть ваше прізвище, ім’я та по батькові:')

@dp.message(Intake.name)
async def name(m:Message,state:FSMContext):
    if not m.text or len(m.text.strip())<4: return await m.answer('Будь ласка, введіть ПІБ повністю.')
    await state.update_data(name=m.text.strip()); await state.set_state(Intake.phone)
    kb=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='Надіслати номер телефону',request_contact=True)]],resize_keyboard=True,one_time_keyboard=True)
    await m.answer('Надішліть номер телефону кнопкою або введіть його вручну:',reply_markup=kb)

@dp.message(Intake.phone)
async def phone(m:Message,state:FSMContext):
    val=m.contact.phone_number if m.contact else (m.text or '').strip()
    if len(re.sub(r'\D','',val))<9: return await m.answer('Перевірте номер телефону та введіть його ще раз.')
    await state.update_data(phone=val); await state.set_state(Intake.service)
    await m.answer('Оберіть потрібну послугу:',reply_markup=service_kb())

def service_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=s,callback_data='svc:'+str(i))] for i,s in enumerate(SERVICES)])
def device_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=s,callback_data='dev:'+str(i))] for i,s in enumerate(DEVICES)])
@dp.callback_query(F.data.startswith('svc:'))
async def service(c:CallbackQuery,state:FSMContext):
    if await state.get_state()!=Intake.service.state: return await c.answer()
    v=SERVICES[int(c.data.split(':')[1])]; await state.update_data(service=v); await state.set_state(Intake.device)
    await c.message.edit_text(f'Обрана послуга: {v}\n\nОберіть тип приладу обліку:',reply_markup=device_kb()); await c.answer()
@dp.callback_query(F.data.startswith('dev:'))
async def device(c:CallbackQuery,state:FSMContext):
    if await state.get_state()!=Intake.device.state: return await c.answer()
    v=DEVICES[int(c.data.split(':')[1])]; await state.update_data(device=v); await state.set_state(Intake.address)
    await c.message.edit_text(f'Тип приладу: {v}'); await c.message.answer('Вкажіть адресу об’єкта, де потрібна послуга:'); await c.answer()
@dp.message(Intake.address)
async def address(m:Message,state:FSMContext):
    if not m.text or len(m.text.strip())<5: return await m.answer('Вкажіть, будь ласка, повну адресу об’єкта.')
    await state.update_data(address=m.text.strip()); await state.set_state(Intake.quantity)
    await m.answer('Скільки приладів потрібно обслужити / встановити? Вкажіть число:')
@dp.message(Intake.quantity)
async def quantity(m:Message,state:FSMContext):
    if not m.text or not m.text.strip().isdigit() or int(m.text.strip())<1: return await m.answer('Введіть ціле число, не менше 1.')
    await state.update_data(quantity=int(m.text.strip())); await state.set_state(Intake.details)
    await m.answer('За бажанням вкажіть марку, модель або серійний номер приладу. Якщо не знаєте — напишіть «Немає».')
@dp.message(Intake.details)
async def details(m:Message,state:FSMContext):
    await state.update_data(details=(m.text or 'Немає').strip()); d=await state.get_data(); await state.set_state(Intake.confirm)
    summary=(f'Перевірте дані заявки:\n\nПІБ: {d["name"]}\nТелефон: {d["phone"]}\nПослуга: {d["service"]}\nТип приладу: {d["device"]}\nАдреса об’єкта: {d["address"]}\nКількість: {d["quantity"]}\nМарка / модель / серійний номер: {d["details"]}')
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Підтвердити',callback_data='confirm'),InlineKeyboardButton(text='Скасувати',callback_data='abort')]])
    await m.answer(summary,reply_markup=kb)

@dp.callback_query(F.data=='abort')
async def abort(c:CallbackQuery,state:FSMContext):
    await state.clear(); await c.message.edit_text('Заявку скасовано. Щоб оформити нову, натисніть «Подати заявку».'); await c.answer()
@dp.callback_query(F.data=='confirm')
async def confirm(c:CallbackQuery,state:FSMContext):
    if await state.get_state()!=Intake.confirm.state: return await c.answer()
    d=await state.get_data(); d.update(user_id=c.from_user.id,username=c.from_user.username or '',created=datetime.now().isoformat(timespec='seconds'))
    app_id=db.create(d); d['id']=app_id
    try: contract=create_contract(d)
    except Exception as e:
        logging.exception('contract generation failed')
        await c.answer('Не вдалося сформувати чернетку договору. Зверніться до менеджера.',show_alert=True); return
    db.set_contract(app_id,str(contract))
    await c.message.edit_text('Заявку прийнято')
    # Send complete application and draft contract together to the manager.
    body=(f'НОВА ЗАЯВКА №{app_id}\nПІБ: {d["name"]}\nТелефон: {d["phone"]}\nTelegram: @{d["username"] or "не вказано"}\nПослуга: {d["service"]}\nТип приладу: {d["device"]}\nАдреса об’єкта: {d["address"]}\nКількість: {d["quantity"]}\nМарка / модель / серійний номер: {d["details"]}\n\nСтатус: очікує рішення менеджера.')
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Замінити DOCX договору',callback_data=f'replace:{app_id}')],[InlineKeyboardButton(text='Затвердити заявку',callback_data=f'approve:{app_id}'),InlineKeyboardButton(text='Відхилити',callback_data=f'reject:{app_id}')]])
    await bot.send_message(MANAGER_ID,body,reply_markup=kb)
    await bot.send_document(MANAGER_ID,FSInputFile(contract),caption=f'Чернетка договору до заявки №{app_id}. Перевірте файл перед затвердженням.')
    await state.clear(); await c.answer()

@dp.callback_query(F.data.startswith('replace:'))
async def replace(c:CallbackQuery,state:FSMContext):
    if c.from_user.id!=MANAGER_ID: return await c.answer('Недостатньо прав.',show_alert=True)
    app=int(c.data.split(':')[1]); db.set_manager_mode(c.from_user.id,app)
    await c.message.answer(f'Надішліть новий DOCX-файл договору для заявки №{app} одним документом.')
    await c.answer()
@dp.message(F.document)
async def manager_doc(m:Message):
    if m.from_user.id!=MANAGER_ID: return
    app=db.get_manager_mode(m.from_user.id)
    if not app: return
    if not (m.document.file_name or '').lower().endswith('.docx'):
        return await m.answer('Потрібен файл DOCX. Надішліть документ ще раз.')
    path=Path('data')/f'contract_{app}_manager.docx'; await bot.download(m.document,path)
    db.set_contract(app,str(path)); db.clear_manager_mode(m.from_user.id)
    await m.answer(f'Файл договору для заявки №{app} збережено. Тепер можна затвердити заявку кнопкою в повідомленні з даними.')

@dp.callback_query(F.data.startswith('approve:'))
async def approve(c:CallbackQuery):
    if c.from_user.id!=MANAGER_ID: return await c.answer('Недостатньо прав.',show_alert=True)
    app=int(c.data.split(':')[1]); d=db.get(app)
    if not d: return await c.answer('Заявку не знайдено.',show_alert=True)
    contract=db.get_contract(app)
    if not contract or not Path(contract).exists(): return await c.answer('Файл договору відсутній.',show_alert=True)
    # Never send a contract with unresolved mandatory company/payment/price fields.
    if not os.getenv('COMPANY_IBAN','').strip() or not os.getenv('PRICE_LIST_READY','').lower()=='yes':
        return await c.answer('Заявку можна затвердити після заповнення IBAN і прайсу в .env. Файл клієнту не надсилався.',show_alert=True)
    db.set_status(app,'approved')
    await bot.send_document(d['user_id'],FSInputFile(contract),caption='Ваш договір підготовлено. Будь ласка, перевірте документ.')
    await c.message.answer(f'Заявку №{app} затверджено. Договір надіслано клієнту.')
    await c.answer()
@dp.callback_query(F.data.startswith('reject:'))
async def reject(c:CallbackQuery):
    if c.from_user.id!=MANAGER_ID: return await c.answer('Недостатньо прав.',show_alert=True)
    app=int(c.data.split(':')[1]); d=db.get(app)
    if not d: return await c.answer('Заявку не знайдено.',show_alert=True)
    db.set_status(app,'rejected')
    await bot.send_message(d['user_id'],f'На жаль, вашу заявку відхилено. Якщо у вас є запитання, зв’яжіться з нами: {COMPANY_PHONE}.')
    await c.message.answer(f'Заявку №{app} відхилено. Клієнта повідомлено.')
    await c.answer()

async def main(): await dp.start_polling(bot)
if __name__=='__main__': asyncio.run(main())
