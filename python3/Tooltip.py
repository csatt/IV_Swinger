"""Module to implement tooltips"""
import tkinter.ttk as ttk
import tkinter as tk


class Tooltip():
    """
    Creates a tooltip for a given widget as the mouse moves over it

    see:

    http://stackoverflow.com/questions/3221956/
           what-is-the-simplest-way-to-make-tooltips-
           in-tkinter/36221216#36221216

    http://www.daniweb.com/programming/software-development/
           code/484591/a-tooltip-class-for-tkinter

    - Originally written by vegaseat on 2014.09.09.

    - Modified to include a delay time by Victor Zaccardo on 2016.03.25.

    - Modified
        - to correct extreme right and extreme bottom behavior,
        - to stay inside the screen whenever the tooltip might go out on
          the top but still the screen is higher than the tooltip,
        - to use the more flexible mouse positioning,
        - to add customizable background color, padding, waittime and
          wraplength on creation
      by Alberto Vassena on 2016.11.05.

    - Modified by Chris Satterlee for IV Swinger 2:
        - Converted to Python 2.x
        - Added staytime parameter
        - Added offset_up and offset_left parameters
    """
    # pylint: disable=too-many-instance-attributes

    def __init__(self, widget,
                 bg='#FFFFEA',
                 fg='black',
                 pad=(5, 3, 5, 3),
                 text='widget info',
                 waittime=400,
                 wraplength=250,
                 staytime=1000,
                 offset_up=False,
                 offset_left=False):
        # pylint: disable=too-many-arguments
        self.waittime = waittime  # in milliseconds, originally 500
        self.wraplength = wraplength  # in pixels, originally 180
        self.staytime = staytime  # in milliseconds per char
        self.offset_up = offset_up
        self.offset_left = offset_left
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.on_enter)
        self.widget.bind("<Leave>", self.on_leave)
        self.widget.bind("<ButtonPress>", self.on_leave)
        self.bg = bg
        self.fg = fg
        self.pad = pad
        self.id = None
        self.tw = None

    def on_enter(self, event=None):
        """Method to perform actions when mouse pointer enters the widget
        """
        # pylint: disable=unused-argument
        self.schedule()
        total_staytime = self.staytime * max(len(self.text), 30)
        canceltime = self.waittime + total_staytime
        self.widget.after(canceltime, self.hide)

    def on_leave(self, event=None):
        """Method to perform actions when mouse pointer leaves the widget
        """
        # pylint: disable=unused-argument
        self.unschedule()
        self.hide()

    def schedule(self):
        """Method to schedule showing the tooltip"""
        self.unschedule()
        self.id = self.widget.after(self.waittime, self.show)

    def unschedule(self):
        """Method to cancel showing the tooltip"""
        id_ = self.id
        self.id = None
        if id_:
            self.widget.after_cancel(id_)

    def show(self):
        """Method to show the tooltip"""
        def tip_pos_calculator(widget, label,
                               tip_delta=(70, 5), pad=(5, 3, 5, 3)):
            """Local function to calculate the position of the tooltip"""
            # pylint: disable=too-many-locals

            w = widget

            s_width, s_height = w.winfo_screenwidth(), w.winfo_screenheight()

            width, height = (pad[0] + label.winfo_reqwidth() + pad[2],
                             pad[1] + label.winfo_reqheight() + pad[3])

            mouse_x, mouse_y = w.winfo_pointerxy()

            x1, y1 = mouse_x + tip_delta[0], mouse_y + tip_delta[1]
            if self.offset_left:
                x1 = mouse_x - tip_delta[0] - width
            if self.offset_up:
                y1 = mouse_y - tip_delta[1] - height

            x2, y2 = x1 + width, y1 + height

            x_delta = x2 - s_width
            if x_delta < 0:
                x_delta = 0
            y_delta = y2 - s_height
            if y_delta < 0:
                y_delta = 0

            offscreen = (x_delta, y_delta) != (0, 0)

            if offscreen:

                if x_delta:
                    x1 = mouse_x - tip_delta[0] - width

                if y_delta:
                    y1 = mouse_y - tip_delta[1] - height

            offscreen_again = y1 < 0  # out on the top

            if offscreen_again:
                # No further checks will be done.

                # TIP:
                # A further mod might automagically augment the
                # wraplength when the tooltip is too high to be
                # kept inside the screen.
                y1 = 0

            return x1, y1

        bg = self.bg
        fg = self.fg
        pad = self.pad
        widget = self.widget

        # creates a toplevel window
        self.tw = tk.Toplevel(widget)

        # Leaves only the label and removes the app window
        self.tw.wm_overrideredirect(True)

        win = tk.Frame(self.tw,
                       background=bg,
                       borderwidth=0)
        label = tk.Label(win,
                         text=self.text,
                         justify=tk.LEFT,
                         background=bg,
                         foreground=fg,
                         relief=tk.SOLID,
                         borderwidth=0,
                         wraplength=self.wraplength)

        label.grid(padx=(pad[0], pad[2]),
                   pady=(pad[1], pad[3]),
                   sticky=tk.NSEW)
        win.grid()

        x, y = tip_pos_calculator(widget, label)

        self.tw.wm_geometry("+{}+{}".format(x, y))

    def hide(self):
        """Method to remove the tooltip"""
        tw = self.tw
        if tw:
            tw.destroy()
        self.tw = None


if __name__ == '__main__':

    import random

    def further_text():
        """Method to generate random dummy text, for standalone testing"""
        # texts generated at http://lorem-ipsum.perbang.dk/
        short_text = ('Lorem ipsum dolor sit amet, mauris tellus, '
                      'porttitor torquent eu. Magna aliquet lorem, '
                      'cursus sit ac, in in. Dolor aliquet, cum integer. '
                      'Proin aliquet, porttitor pulvinar mauris. Tellus '
                      'lectus, amet cras, neque lacus quis. Malesuada '
                      'nibh. Eleifend nam, in eget a. Nec turpis, erat '
                      'wisi semper')
        medium_text = ('Lorem ipsum dolor sit amet, suspendisse aenean '
                       'ipsum sollicitudin, pellentesque nunc ultrices ac '
                       'ut, arcu elit turpis senectus convallis. Ac orci '
                       'pretium sed gravida, tortor nulla felis '
                       'consectetuer, mauris egestas est erat. Ut enim '
                       'tellus at diam, ac sagittis vel proin. Massa '
                       'eleifend orci tortor sociis, scelerisque in pede '
                       'metus phasellus, est tempor gravida nam, ante '
                       'fusce sem tempor. Mi diam auctor vel pede, mus '
                       'non mi luctus luctus, lectus sit varius repellat '
                       'eu')
        long_text = ('Lorem ipsum dolor sit amet, velit eu nam cursus '
                     'quisque gravida sollicitudin, felis arcu interdum '
                     'error quam quis massa, et velit libero ligula est '
                     'donec. Suspendisse fringilla urna ridiculus dui '
                     'volutpat justo, quisque nisl eget sed blandit '
                     'egestas, libero nullam magna sem dui nam, auctor '
                     'vehicula nunc arcu vel sed dictum, tincidunt vitae '
                     'id tristique aptent platea. Lacus eros nec proin '
                     'morbi sollicitudin integer, montes suspendisse '
                     'augue lorem iaculis sed, viverra sed interdum eget '
                     'ut at pulvinar, turpis vivamus ac pharetra nulla '
                     'maecenas ut. Consequat dui condimentum lectus nulla '
                     'vitae, nam consequat fusce ac facilisis eget orci, '
                     'cras enim donec aenean sed dolor aliquam, elit '
                     'lorem in a nec fringilla, malesuada curabitur diam '
                     'nonummy nisl nibh ipsum. In odio nunc nec porttitor '
                     'ipsum, nunc ridiculus platea wisi turpis praesent '
                     'vestibulum, suspendisse hendrerit amet quis vivamus '
                     'adipiscing elit, ut dolor nec nonummy mauris nec '
                     'libero, ad rutrum id tristique facilisis sed '
                     'ultrices. Convallis velit posuere mauris lectus sit '
                     'turpis, lobortis volutpat et placerat leo '
                     'malesuada, vulputate id maecenas at a volutpat '
                     'vulputate, est augue nec proin ipsum pellentesque '
                     'fringilla. Mattis feugiat metus ultricies repellat '
                     'dictum, suspendisse erat rhoncus ultricies in ipsum, '
                     'nulla ante pellentesque blandit ligula sagittis '
                     'ultricies, sed tortor sodales pede et duis platea')

        text = random.choice([short_text, medium_text, long_text, long_text])

        return '\nFurther info: ' + text

    def main_01(wraplength=200):
        """Method for standalone testing"""
        # pylint: disable=too-many-locals

        # alias
        stuff = further_text

        root = tk.Tk()
        frame = ttk.Frame(root)

        btn_ne = ttk.Button(frame, text='North East')
        btn_se = ttk.Button(frame, text='South East')
        btn_sw = ttk.Button(frame, text='South West')
        btn_nw = ttk.Button(frame, text='North West')
        btn_center = ttk.Button(frame, text='Center')
        btn_n = ttk.Button(frame, text='North')
        btn_e = ttk.Button(frame, text='East')
        btn_s = ttk.Button(frame, text='South')
        btn_w = ttk.Button(frame, text='West')

        Tooltip(btn_nw, text='North West' + stuff(), wraplength=wraplength,
                offset_up=True)
        Tooltip(btn_ne, text='North East' + stuff(), wraplength=wraplength)
        Tooltip(btn_se, text='South East' + stuff(), wraplength=wraplength)
        Tooltip(btn_sw, text='South West' + stuff(), wraplength=wraplength)
        Tooltip(btn_center, text='Center' + stuff(), wraplength=wraplength)
        Tooltip(btn_n, text='North' + stuff(), wraplength=wraplength)
        Tooltip(btn_e, text='East' + stuff(), wraplength=wraplength)
        Tooltip(btn_s, text='South' + stuff(), wraplength=wraplength)
        Tooltip(btn_w, text='West' + stuff(), wraplength=wraplength,
                offset_left=True)

        r = 0
        c = 0
        pad = 10
        btn_nw.grid(row=r, column=c, padx=pad, pady=pad, sticky=tk.NW)
        btn_n.grid(row=r, column=c + 1, padx=pad, pady=pad, sticky=tk.N)
        btn_ne.grid(row=r, column=c + 2, padx=pad, pady=pad, sticky=tk.NE)

        r += 1
        btn_w.grid(row=r, column=c + 0, padx=pad, pady=pad, sticky=tk.W)
        btn_center.grid(row=r, column=c + 1, padx=pad, pady=pad,
                        sticky=tk.NSEW)
        btn_e.grid(row=r, column=c + 2, padx=pad, pady=pad, sticky=tk.E)

        r += 1
        btn_sw.grid(row=r, column=c, padx=pad, pady=pad, sticky=tk.SW)
        btn_s.grid(row=r, column=c + 1, padx=pad, pady=pad, sticky=tk.S)
        btn_se.grid(row=r, column=c + 2, padx=pad, pady=pad, sticky=tk.SE)

        frame.grid(sticky=tk.NSEW)
        for i in (0, 2):
            frame.rowconfigure(i, weight=1)
            frame.columnconfigure(i, weight=1)

        root.rowconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)

        root.title('Tooltip wraplength = {}'.format(wraplength))
        root.mainloop()

    def main():
        """Main method, for standalone testing"""
        print('Trying out three different wraplengths:')
        for i, wl in enumerate((200, 250, 400), 1):
            print(' ', i)
            main_01(wl)
        print('Done.')

    main()
