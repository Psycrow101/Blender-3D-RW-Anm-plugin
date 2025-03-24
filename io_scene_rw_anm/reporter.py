import bpy


class Reporter:
    def __init__(self, title):
        self.title = title
        self.imported_actions_num = 0
        self.exported_actions_num = 0
        self._warnings = []
        self._errors = []

    def warning(self, *string):
        message = " ".join(str(s) for s in string)
        print("WARNING:", message)
        self._warnings.append(message)

    def error(self, *string):
        message = " ".join(str(s) for s in string)
        print("ERROR:", message)
        self._errors.append(message)

    def draw_layout(self, menu, context):
        layout = menu.layout

        if self._errors:
            for msg in self._errors:
                layout.label(text="Error: %s" % msg, icon='ERROR')
            layout.separator()

        if self._warnings:
            for msg in self._warnings:
                layout.label(text="Warning: %s" % msg, icon='ERROR')
            layout.separator()

        if self.imported_actions_num:
            layout.label(text="Imported %d actions" % self.imported_actions_num, icon='INFO')

        if self.exported_actions_num:
            layout.label(text="Exported %d actions" % self.exported_actions_num, icon='INFO')

    def show(self):
        if not bpy.app.background:
            bpy.context.window_manager.popup_menu(self.draw_layout, title=self.title)
