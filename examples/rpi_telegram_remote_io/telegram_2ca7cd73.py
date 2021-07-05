import logging, queue
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters, CallbackQueryHandler
from enum import Enum
try:
    from element_types import Record, Function, ProcCMD, GuiCMD, SetPersist
except ImportError:    
    from Pythonic.element_types import Record, Function, ProcCMD, GuiCMD, SetPersist

try:
    from element_types import Record, Function, ProcCMD, GuiCMD
except ImportError:    
    from Pythonic.element_types import Record, Function, ProcCMD, GuiCMD


class GPIO_State(Enum):
    On  = True
    Off = False


class Element(Function):

    def __init__(self, id, config, inputData, return_queue, cmd_queue):
        super().__init__(id, config, inputData, return_queue, cmd_queue)


    def execute(self):

        #####################################
        #                                   #
        #     REFERENCE IMPLEMENTATION      #
        #                                   #
        #####################################

        cmd             = None
        specificConfig  = self.config.get('SpecificConfig')
        chat_ids        = SetPersist('chat_ids')

        self.gpio4_state     = GPIO_State.Off.value
        self.gpio5_state     = GPIO_State.Off.value
        self.gpio4_button    = KeyboardButton(text='Switch GPIO4 {}'.format(GPIO_State(not self.gpio4_state).name, callback_data=4))
        self.gpio5_button    = KeyboardButton(text='Switch GPIO5 {}'.format(GPIO_State(not self.gpio5_state).name, callback_data=5))
        self.keyboard        = ReplyKeyboardMarkup.from_column([self.gpio4_button, self.gpio5_button], one_time_keyboard=True)

        if not specificConfig:

            recordDone = Record(None, message='Config missing')
            self.return_queue.put(recordDone)
            return


        token = next(attr['Data'] for attr in specificConfig if attr['Name'] == 'Token')

        if not token:
            recordDone = Record(None, message='Token missing')
            self.return_queue.put(recordDone)
            return

        updater = Updater(token=self.config['SpecificConfig'][0]['Data'], use_context=True)

        dispatcher = updater.dispatcher


        def start(update: Update, context: CallbackContext):
            
            chat_ids.add(update.message.chat_id) 
            
            context.bot.sendMessage(update.effective_chat.id, 'Start remote control GPIO', reply_markup=self.keyboard)

        def unknown(update, context):
            context.bot.send_message(chat_id=update.effective_chat.id, text='Sorry, I didn\'t understand that command.')

        def message(update, context):
            context.bot.send_message(chat_id=update.effective_chat.id, text='Message received')

            msg = update.message.text

            #guitext = GuiCMD('Message received from: {}, MsgId.: {:d}'.format(update.message.from_user.first_name, update.message.message_id))
            #self.return_queue.put(guitext)
            record = Record(update.message, 'Message received from: {}, MsgId.: {:d}'.format(update.message.from_user.first_name, update.message.message_id))
            self.return_queue.put(record)


        """
        def callback(update: Update, context: CallbackContext):
            callback_type = update.callback_query.data

            if callback_type == '4':
                self.gpio4_state = not self.gpio4_state
                context.bot.sendMessage(update.effective_chat.id, 'Set GPIO 4 to {}'.format(GPIO_State(self.gpio4_state).name), reply_markup=self.keyboard)
                return
            elif callback_type == '5':
                self.gpio5_state = not self.gpio5_state
                context.bot.sendMessage(update.effective_chat.id, 'Set GPIO 5 to {}'.format(GPIO_State(self.gpio5_state).name), reply_markup=self.keyboard)
                return
            else:
                context.bot.sendMessage(update.effective_chat.id, 'Unknown GPIO type in callback - doing nothing')
        """

        start_handler       = CommandHandler('start', start)
        message_handler     = MessageHandler(Filters.text &~ Filters.command, message)
        unknown_cmd_handler = MessageHandler(Filters.command, unknown)
        #callback_handler    = CallbackQueryHandler(callback)

        dispatcher.add_handler(start_handler)
        dispatcher.add_handler(message_handler) # muss als letztes hinzugefügt werden
        dispatcher.add_handler(unknown_cmd_handler)
        #dispatcher.add_handler(callback_handler)
        

        updater.start_polling()

        while(updater.running):
            
            try:
                # Block for 1 second and wait for incoming commands 
                cmd = self.cmd_queue.get(block=True, timeout=1)
            except queue.Empty:
                pass

            if isinstance(cmd, ProcCMD) and cmd.bStop:
                # Stop command received, exit
                updater.stop()

            elif isinstance(cmd, ProcCMD):

                guitext = GuiCMD("Sending data: " + str(cmd.data))
                self.return_queue.put(guitext)

                for chat_id in chat_ids:
                    try:
                        dispatcher.bot.send_message(chat_id=chat_id, text=str(cmd.data))
                    except Exception as e:
                        logging.error(e)
                        chat_ids.discard(chat_id)
                        logging.warning('ChatId removed')
                    


            cmd = None

