import pygame
import os
import os.path
import json
import fparser

#print(pygame.font.get_fonts())

SCREENSIZE = (1280, 720)
pygame.display.set_caption("Faf VN Framework")
window = pygame.display.set_mode(SCREENSIZE)
SCREEN_RECT = window.get_rect()

NAME_FONT = pygame.font.Font
SAY_FONT = pygame.font.Font

POSITION = dict()
with open("./Params/positions.json") as file:
    POSITION = json.load(file)

COLOR = dict()
with open("./Assets/Chara/colors.json") as file:
    COLOR = json.load(file)

eventList = list()  # Copy of pygame.event.get()

uiDebug = dict()

charaZBuffer = list()   # Stores a reference to what's drawn, in which order
uiZBuffer = list()
textBuffer = list() # Stores every text drawn on screen

class Scene():
    cg = None
    bg = None
    data = dict()
    GOTO = list()   # Where to go next
    SBID = "0"    # Stores the current Story Block ID
    CHARACTERS = tuple()
    characterBuffer = dict()    # Stores the current characters
    previousBGwasCG = False   # Stores a bool that indicates if the previous BG was CG
    currentScriptLineType = None
    scriptBuffer = list() # Stores all the speaches in the current SBID
    script_index = int()
    choiceBuffer = []
    vars = {}   # Stores all the variables
    lastCharaDrawnSpeech = pygame.surface.Surface
    
    
    writeCounter = 0
    writingSpeed = 3
    isDoneWriting = False
    skipWriting = False
    
    paused = False  # Pauses the scene when there's a choice for example
    appreciating = False    # Whether or not the user is in appreciation mode
    inMenu = False  # Whether or not the user is in a menu

    # OPTIONS

    EnableParallax = True
    
    def load(chapter : str, SBID = "0", script_index = 0):
        Scene.script_index = script_index  # DO NOT REMOVE (it also resets it when changing Chapters)
        fparser.Parser.loadChapter(f"./Story/{chapter}.fvnc")
        
        Scene.data = fparser.chapter[SBID]
        Scene.GOTO = Scene.data["GOTO"]
        Scene.scriptBuffer = Scene.data["SCRIPT"]
        Scene.loadCharacters()
        
        Scene.bg = pygame.image.load(Scene.data["BG"]).convert()
        window.blit(Scene.bg, (0, 0))
    
    def advance():
        if not Scene.isDoneWriting: # If it's not done writing but you want to advance, it'll write everything
            Scene.skipWriting = True
        else :
            Scene.script_index += 1
            Scene.skipWriting = False
            Scene.isDoneWriting = False
            Scene.writeCounter = 0
            
            if Scene.script_index >= len(Scene.scriptBuffer):    # If we reach the end of the SBID
                if "NEXT" in Scene.data.keys(): # If we reach the end of the Chapter
                    Scene.load(Scene.data["NEXT"][0], Scene.data["NEXT"][1])
                else:   
                    if len(Scene.GOTO) != 1:    # aka if it's a CHOICE
                        Scene.choice()
                    else:   # Otherwise, we just read the next Story Block
                        Scene.nextStoryBlock()
    
    def appreciationMode():
        """Hides the UI and pauses the game to appreciate the artworks"""
        if Scene.appreciating:
            Scene.paused = False
            Scene.appreciating = False
        else:
            Scene.appreciating = True
            Scene.paused = True
    
    def nextStoryBlock(sbid = None):
        Scene.paused = False
        Scene.script_index = 0  # resets the Script Index
        if sbid == None:
            Scene.data = fparser.chapter[Scene.GOTO[0][0]]  # GOTO : [(SBID, Transition)]
        else:   #or when it's a CHOICE, the SBID of the choice
            Scene.data = fparser.chapter[sbid]
        Scene.GOTO = Scene.data["GOTO"]        
        Scene.scriptBuffer = Scene.data["SCRIPT"]
        print(Scene.data["SCRIPT"])
        if len(Scene.data["CHARACTERS"]) != 0:  # If the Character List changed
            Scene.loadCharacters()
        
        Scene.bg = pygame.image.load(Scene.data["BG"]).convert()
        window.blit(Scene.bg, (0, 0))
    
    def choice():
        Scene.paused = True
        textBuffer.append(Scene.lastCharaDrawnSpeech)   # Restores the last Chara Speech
        option_spacing = 80
        option_count = len(Scene.GOTO)
        if option_count == 2:   # When there's only 2 options, centering with option_spacing*i + SCREENSIZE[1] / len(Scene.GOTO) doesn't work
            for i in range(option_count):
                option = Scene.GOTO[i]
                print(option)
                Scene.choiceBuffer.append(UIButton(option[1], option[0], option[2], pos=(0, option_spacing*i + SCREENSIZE[1] / 2.5)))
        else:
            for i in range(option_count):
                option = Scene.GOTO[i]
                Scene.choiceBuffer.append(UIButton(option[1], option[0], option[2], pos=(0, option_spacing*i + SCREENSIZE[1] / len(Scene.GOTO))))    # <= choiceBuffer[Label] : (SBID, {vars})
        print(f"Scene VARIABLES : {Scene.vars}")
    
    def cleanChoiceBuffer():
        for option in Scene.choiceBuffer:
            option.free()
        Scene.choiceBuffer = list()
    
    def readScript():
        scriptLine = Scene.scriptBuffer[Scene.script_index]

        Scene.currentScriptLineType = type(scriptLine)

        if Scene.currentScriptLineType not in [fparser.AbstractNarratorLine, fparser.AbstractCG, fparser.IfStatement]: # If the the current line type isn't one of them, unload the CG.
            Scene.unloadCG()
        
        match type(scriptLine):
            case fparser.AbstractCharaAction:
                Scene.characterBuffer[scriptLine.chara].set_expression(scriptLine.expression)
                Scene.characterBuffer[scriptLine.chara].say(scriptLine.action)
            case fparser.AbstractCharaLine:
                Scene.characterBuffer[scriptLine.chara].set_expression(scriptLine.expression)
                Scene.characterBuffer[scriptLine.chara].say(scriptLine.line)
            case fparser.AbstractNarratorLine:
                Scene.say(scriptLine.line)
            case fparser.AbstractCG:
                Scene.loadCG(scriptLine.path)
            case fparser.IfStatement:
                Scene.testFor()
    
    def say(phrase : str):
        text_box = TextWrapper.render_text_list(TextWrapper.wrap_text(phrase, SAY_FONT, UI.boxCharaText.size[0]), SAY_FONT, COLOR["$Narrator"])
        narrator_name = NAME_FONT.render("Narrator", True, COLOR["$Narrator"])
        textBuffer.append((narrator_name, UIBox.center(UI.boxCharaName, narrator_name)))    # (Surface, Rect)
        textBuffer.append((text_box, (180, 592)))   # (Surface, Rect)
        Scene.lastCharaDrawnSpeech = (text_box, (180, 592))
    
    def sayCG(phrase : str):
        text_box = TextWrapper.render_text_list(TextWrapper.wrap_text(phrase, SAY_FONT, UI.boxCharaText.size[0]), SAY_FONT, COLOR["$Narrator"])
        textBuffer.append((text_box, (180, 592)))   # (Surface, Rect)
        Scene.lastCharaDrawnSpeech = (text_box, (180, 592))
    
    def loadCG(path : str):
        Scene.cg = pygame.image.load(path).convert()
        Scene.sayCG("...")
    
    def unloadCG() -> None:
        Scene.cg = None
    
    def testFor():
        ifStatement = Scene.scriptBuffer[Scene.script_index]
        
        print(ifStatement)
        
        valid = True
        
        if len(Scene.vars) == 0:
            Scene.script_index += 1
        else:
            for key in ifStatement.vars.keys():
                if key in Scene.vars.keys():
                    if ifStatement.vars[key] != Scene.vars[key]:
                        valid = False
            if valid:
                    Scene.nextStoryBlock(ifStatement.goto)
            else:
                Scene.script_index += 1
    
    def loadCharacters():
        previousCharaList = Scene.characterBuffer.keys()
        abstractCharacters = Scene.data["CHARACTERS"]
        newCharaList = [newChara[0] for newChara in abstractCharacters]
        for oldChara in previousCharaList:
            if not oldChara in newCharaList:    # Do we need to free the character
                Scene.characterBuffer[oldChara].free()
        
        tmpCharacterBuffer = dict()
        
        for chara in abstractCharacters:
            if chara[0] in previousCharaList:   # If in already exists, take the old one
                tmpCharacterBuffer[chara[0]] = Scene.characterBuffer[chara[0]]
                tmpCharacterBuffer[chara[0]].set_expression(chara[1])
                tmpCharacterBuffer[chara[0]].set_pos(POSITION[chara[2]])
            else:   # Otherwise, creat a new Chara Object
                tmpCharacterBuffer[chara[0]] = Chara(chara[0], POSITION[chara[2]], COLOR[chara[0]], chara[1])
            print(f"CHARA {chara[0]}.{chara[1]} loaded")
        
        Scene.characterBuffer = tmpCharacterBuffer
        
        print(f"Active Character Objects : {Chara.count}")

    def parallaxEffect():
        max_offset = 10
        screen_center = SCREEN_RECT.center

        mouse_pos = pygame.mouse.get_pos()
        for i in range(1, len(charaZBuffer)+1):
            charaZBuffer[i-1].apply_parallax(int(-1 * (mouse_pos[0] - screen_center[0]) * max_offset / screen_center[0]), int(-1 * (mouse_pos[1] - screen_center[1]) * max_offset / screen_center[1]))
        #chara.pos.x = -1 * (mouse_pos[0] - screen_center[0]) * max_offset / screen_center[0]
        #chara.pos.y = -1 * (mouse_pos[1] - screen_center[1]) * max_offset / screen_center[1]
        #print(f"{(mouse_pos[0] - screen_center[0]) * max_offset / screen_center[0]}, {(mouse_pos[1] - screen_center[1]) * max_offset / screen_center[1]}")

    def checkCollisions():
        if len(Scene.choiceBuffer) != 0:
            for button in Scene.choiceBuffer:
                button.isClicked()
    def update():     
        # The background is always drawn first
        window.blit(Scene.bg, (0, 0))
        
        if Scene.EnableParallax:
            Scene.parallaxEffect()

        # Then the characters
        for chara in charaZBuffer:
            chara.update()
            #window.blit(chara.sprite, chara.pos)
        
        print(charaZBuffer)
        
        # Then the CG if there are any
        if Scene.cg != None:
            window.blit(Scene.cg, (0, 0))

        # Then the UI
        if not Scene.paused:
            Scene.readScript()
            Scene.previousScriptLineType = type(Scene.scriptBuffer[Scene.script_index])
        UI.update()

class UIBox():
    name = str()
    size = tuple()
    box = None
    center = None
    pos = None
    rect = pygame.rect.Rect
    forDebug = bool
    
    def __init__(self, name : str, size : tuple, pos  = (0, 0), color = (255, 0, 0, 50), centered = 0, forDebug = True) -> None:
        self.name = name
        self.size = size
        self.box = pygame.Surface(size).convert_alpha()
        self.box.fill(color)
        self.forDebug = forDebug
        tmp_pos = self.box.get_rect()
        
        match centered:
            case 0:
                self.pos = pos
            case 1:
                self.pos = self.box.get_rect(center = (SCREEN_RECT.centerx, tmp_pos.centery))
            case 2:
                self.pos = self.box.get_rect(center = (tmp_pos.centerx, SCREEN_RECT.centery))
            case 3:
                self.pos = self.box.get_rect(center = SCREEN_RECT.center)
        
        if not centered:
            self.pos = pos
            self.rect = self.box.get_rect()
        else:
            self.pos = self.pos.move(pos[0], pos[1])
            self.rect = self.pos
            self.pos = (self.pos.x, self.pos.y)
        self.center = self.box.get_rect().center
        
        if forDebug:
            uiDebug[self.name] = self
    
    def center(parent, child : pygame.Surface):
        return child.get_rect(center = parent.center).move(parent.pos)
        
class UIButton(UIBox):
    label = str()
    sbid = str()
    vars = dict()
    renderedLabel = pygame.surface.Surface
    
    def __init__(self, name: str, sbid : str, vars : dict, pos= (0, 0), size = (400, 50), color=(0, 0, 0, 120), centered=1, forDebug=False) -> None:
        self.label = name
        self.sbid = sbid
        self.vars = vars
        super().__init__(name, size, pos, color, centered, forDebug)
        
        self.renderedLabel = SAY_FONT.render(self.label, True, (255, 255, 255))
        textBuffer.append((self.renderedLabel, UIBox.center(self, self.renderedLabel))) # (Surface, Rect)
    
    def isClicked(self):
        mousePos = pygame.mouse.get_pos()
        if self.rect.collidepoint(mousePos):
            for event in eventList:
                if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                    for key, value in self.vars.items():
                        Scene.vars[key] = value
                    Scene.nextStoryBlock(self.sbid)
                    Scene.cleanChoiceBuffer()
    
    def update(self):
        window.blit(self.box, self.pos)
    
    def free(self):
        del self
        
class UI():
    debug = False
    
    boxCharaName = UIBox("BoxCharaName", (181, 39), (140, 532))
    boxCharaText = UIBox("BoxCharaText", (920, 86), (0, 590), centered=1)
    
    def update():
        # If the user isn't in appreciation mode, draw the UI
        if not Scene.appreciating:
            # Ui is always drawn last, but we draw buttons before text
            if len(Scene.choiceBuffer) != 0:    # Handled outside of the uiZBuffer for convenience
                for button in Scene.choiceBuffer:
                    button.update()
            
            # If it's showing a CG, hide the CharaTextBox and other graphical elements
            if Scene.currentScriptLineType != fparser.AbstractCG:
                for elt in uiZBuffer:
                    elt.update()
                
            # Then, text is drawn
            for text in textBuffer:
                window.blit(text[0], text[1]) # (RenderedText : Surface, Postion : Rect)
                if not Scene.paused:    # You mustn't remove even when the scene is paused.
                    textBuffer.remove(text)

            # If Debug mode is on, draws the UI Debug Boxes
            if UI.debug:
                for key in uiDebug.keys():
                    window.blit(uiDebug[key].box, uiDebug[key].pos)       

class UIElement():
    sprite = None
    pos = None
    rot = 0.0
    size = 1
    
    def __init__(self, sprite : str, initPos = (0, 0)) -> None:
        self.sprite = pygame.transform.rotozoom(pygame.image.load(sprite).convert_alpha(), self.rot, self.size)
        self.pos = self.sprite.get_rect().move(initPos)
        uiZBuffer.append(self)
    
    def update(self):
        window.blit(self.sprite, self.pos)
    
    def move(self, dx : int, dy : int):
        self.pos = self.pos.move(dx, dy)

class Chara():
    count = 0
    charaFolder = "./Assets/Chara/"
    name = str()
    expression = dict()
    sprite = None
    preParallaxPos = None
    pos = None
    size = 0.2
    rot = 0.0
    color = tuple()
    
    def __init__(self, name : str, initPos = (80, 20), color = (255, 255, 255), expression = "normal") -> None:
        self.name = name
        self.expression = {sprite.split('.')[0].split("_")[1] : pygame.transform.rotozoom(pygame.image.load(f"{self.charaFolder}{name}/{sprite}").convert_alpha(), self.rot, self.size) for sprite in os.listdir(self.charaFolder + name)}
        self.color = color
        self.sprite = self.expression[expression]
        self.set_pos(initPos)
        
        charaZBuffer.append(self)        
        Chara.count += 1
    
    def __repr__(self):
        return self.name
    
    def update(self):
        window.blit(self.sprite, self.pos)
        self.pos = self.preParallaxPos
    
    def apply_parallax(self, dx : int, dy :int):
        self.move(dx, dy)
    
    def set_expression(self, expression : str):
        self.sprite = self.expression[expression]
    
    def set_pos(self, pos):
        self.pos = self.sprite.get_rect().move(pos)
        self.preParallaxPos = self.pos
    
    def move(self, dx : int, dy : int):
        self.pos = self.pos.move(dx, dy)
    
    def say(self, phrase : str):
        text_box = TextWrapper.render_text_list(TextWrapper.wrap_text(phrase, SAY_FONT, UI.boxCharaText.size[0]), SAY_FONT, self.color)
        chara_name = NAME_FONT.render(self.name, True, self.color)
        textBuffer.append((chara_name, UIBox.center(UI.boxCharaName, chara_name)))    # (Surface, Rect)
        textBuffer.append((text_box, (180, 592)))   # (Surface, Rect)
        Scene.lastCharaDrawnSpeech = (text_box, (180, 592))
    
    def free(self):
        charaZBuffer.remove(self)
        Chara.count -= 1
        del self

class TextWrapper():
    def wrap_text(text, font, width):
        """Wrap text to fit inside a given width when rendered.

        :param text: The text to be wrapped.
        :param font: The font the text will be rendered in.
        :param width: The width to wrap to.

        """
        # EDITED BY FAF for Smooth Writing
        Scene.speechLength = len(text)
        
        if Scene.writeCounter < Scene.writingSpeed * len(text):
            Scene.writeCounter += 1
        elif Scene.writeCounter >= Scene.writingSpeed * len(text):
            Scene.isDoneWriting = True
        
        if not Scene.skipWriting:
            text = text[0:Scene.writeCounter//Scene.writingSpeed]    
        
        # ORIGINAL
        text_lines = text.replace('\t', '    ').split('\n')
        if width is None or width == 0:
            return text_lines

        wrapped_lines = []
        for line in text_lines:
            line = line.rstrip() + ' '
            if line == ' ':
                wrapped_lines.append(line)
                continue

            # Get the leftmost space ignoring leading whitespace
            start = len(line) - len(line.lstrip())
            start = line.index(' ', start)
            while start + 1 < len(line):
                # Get the next potential splitting point
                next = line.index(' ', start + 1)
                if font.size(line[:next])[0] <= width:
                    start = next
                else:
                    wrapped_lines.append(line[:start])
                    line = line[start+1:]
                    start = line.index(' ')
            line = line[:-1]
            if line:
                wrapped_lines.append(line)
        return wrapped_lines


    def render_text_list(lines, font, colour=(255, 255, 255)):
        """Draw multiline text to a single surface with a transparent background.

        Draw multiple lines of text in the given font onto a single surface
        with no background colour, and return the result.

        :param lines: The lines of text to render.
        :param font: The font to render in.
        :param colour: The colour to render the font in, default is white.

        """
        rendered = [font.render(line, True, colour).convert_alpha()
                    for line in lines]

        line_height = font.get_linesize()
        width = max(line.get_width() for line in rendered)
        tops = [int(round(i * line_height)) for i in range(len(rendered))]
        height = tops[-1] + font.get_height()

        surface = pygame.Surface((width, height)).convert_alpha()
        surface.fill((0, 0, 0, 0))
        for y, line in zip(tops, rendered):
            surface.blit(line, (0, y))

        return surface