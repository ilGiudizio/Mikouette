import pygame
import os
import os.path
import json
import fparser
import math
from pygame.math import lerp

## FUNCTIONS
def vector_lerp(a : pygame.math.Vector2, b: pygame.math.Vector2, weight : float):
    return pygame.math.Vector2(lerp(a.x, b.x, weight), lerp(a.y, b.y, weight))

#print(pygame.font.get_fonts())

FPS = 60

SCREENSIZE = (1280, 720)
pygame.display.set_caption("Mikouette")
window = pygame.display.set_mode(SCREENSIZE)
SCREEN_RECT = window.get_rect()

NAME_FONT = pygame.font.Font
SAY_FONT = pygame.font.Font

POSITION = dict()
with open("./Params/positions.json") as file:
    POSITION = json.load(file)
for key in POSITION:
    POSITION[key] = pygame.math.Vector2(POSITION[key][0], POSITION[key][1])

COLOR = dict()
with open("./Assets/Chara/colors.json") as file:
    COLOR = json.load(file)

BMG_BASE_VOLUME = 0.4

eventList = list()  # Copy of pygame.event.get()

uiDebug = dict()

charaZBuffer = list()   # Stores a reference to what's drawn, in which order
uiZBuffer = list()
textBuffer = list() # Stores every text drawn on screen

class BG():
    sprite = pygame.Surface
    rect = pygame.Rect
    preParallaxPos = pygame.math.Vector2
    pos = pygame.math.Vector2
    size = 1.0
    rot = 0.0

    def __init__(self, sprite : str, initPos = (0, 0)) -> None:
        self.sprite = pygame.transform.rotozoom(sprite, self.rot, self.size)
        self.pos = pygame.math.Vector2(initPos[0], initPos[1])
        self.preParallaxPos = self.pos
        self.rect = self.set_rect()
    
    def update(self):
        window.blit(self.sprite, self.pos)
        #print(f"{self.name} || Pre : {self.preParallaxPos} | Post {self.pos}")
        self.pos = self.preParallaxPos
    
    def apply_parallax(self, dx : float, dy : float):
        self.pos = self.preParallaxPos + pygame.Vector2(dx, dy)
        self.rect = round(self.pos.x), round(self.pos.y)
    
    def set_rect(self):
        self.rect = self.sprite.get_rect()
        self.rect.topleft = round(self.pos.x), round(self.pos.y)
    
    def set_pos(self, x : float, y : float):
        self.pos = pygame.math.Vector2(x, y)
        self.preParallaxPos = self.pos
        self.set_rect()
    
    def set_pos(self, pos : tuple):
        self.pos = pygame.math.Vector2(pos[0], pos[1])
        self.preParallaxPos = self.pos
        self.set_rect()
    
    def move(self, dx : float, dy : float):
        self.pos += pygame.Vector2(dx, dy)
        self.rect = round(self.pos.x), round(self.pos.y)

class Scene():
    cg = None
    bg = BG
    data = dict()
    GOTO = list()   # Where to go next
    SBID = "0"    # Stores the current Story Block ID
    CHARACTERS = tuple()
    characterBuffer = dict()    # Stores the current characters {Chara.name : Chara()}
    previousBGwasCG = False   # Stores a bool that indicates if the previous BG was CG
    currentScriptLineType = None
    scriptBuffer = list() # Stores all the speaches in the current SBID
    script_index = int()
    choiceBuffer = []
    vars = {}   # Stores all the variables
    isJojo = False
    ToBeContinued = pygame.transform.rotozoom(pygame.image.load("./Assets/UI/ToBeContinued.png").convert_alpha(), 0, 0.8)
    JojoScreenSurface = pygame.surface.Surface
    lastCharaDrawnSpeech = pygame.surface.Surface

    voicelines = {str : [pygame.mixer.Sound]} # Stores all the voicelines of this chapter
    currentVoiceline = None
    voicelineChannel = pygame.mixer.Channel # Stores the mixer channel of the current voiceline (to know if it's done playing)

    previousMusicPath = None
    musicPath = None

    actionDuration = 3    # in seconds
    isCharaActionDone = False
    lerpWeight = 0.0
    lerpWeightIncrement = 1 / (actionDuration * FPS)
     
    writeCounter = 0
    writingSpeed = 1    # Lower = Faster
    isDoneWriting = False
    hasAlreadyTalked = False
    #isDonePlayingSound = False
    #isDonePlayingVoiceline = False
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

        # BGM
        Scene.loadMusic(True)

        Scene.loadCharacters()
        Scene.loadSounds(chapter)
        
        Scene.bg = BG(pygame.image.load(Scene.data["BG"]).convert()) 
        Scene.bg.update()
    
    def advance():
        if not Scene.isDoneWriting: # If it's not done writing but you want to advance, it'll write everything
            Scene.skipWriting = True
            Scene.lerpWeight = 1.0
        else :
            if Scene.currentVoiceline != None:
                Scene.currentVoiceline.stop()
            Scene.currentVoiceline = None
            Scene.hasAlreadyTalked = False
            #Scene.isDonePlayingSound = False

            Scene.previousMusicPath = Scene.musicPath

            # If it's not done playing the animation when advancing, skips the animation.
            if type(Scene.scriptBuffer[Scene.script_index]) == fparser.AbstractCharaAction:
                Scene.characterBuffer[Scene.scriptBuffer[Scene.script_index].chara].action(Scene.scriptBuffer[Scene.script_index].action, 1.0)

            Scene.lerpWeight = 0.0
            Scene.isCharaActionDone = False

            Scene.script_index += 1
            Scene.skipWriting = False
            Scene.isDoneWriting = False
            Scene.writeCounter = 0
            
            if Scene.script_index >= len(Scene.scriptBuffer):    # If we reach the end of the SBID
                if "NEXT" in Scene.data.keys(): # If we reach the end of the Chapter
                    Scene.voicelines.clear()
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
        
        # BGM
        Scene.loadMusic()
        
        Scene.bg.sprite = pygame.image.load(Scene.data["BG"]).convert()
        Scene.bg.update()
    
    def jojo():
        Scene.appreciating = True
        Scene.isJojo = True

        # Get the pixels
        scaling_factor = 3
        screen_surface = pygame.transform.rotozoom(pygame.display.get_surface(), 0, 1/scaling_factor)    # scales it so it can be done in real time
        pixels = pygame.PixelArray(screen_surface)
        # Iterate over every pixel                                             
        for x in range(screen_surface.get_width()):
            for y in range(screen_surface.get_height()):
                # Turn the pixel data into an RGB tuple
                rgb = screen_surface.unmap_rgb(pixels[x][y])
                # Get a new color object using the RGB tuple and convert to HSLA
                color = pygame.Color(*rgb)
                h, s, v, a = color.hsva
                s = max(0, min(100, int(s) - 20))
                v = max(0, min(100, int(v) + 10))
                # Removes 120 to the hue (or however much you want) and wrap to under 360
                color.hsva = (int(h) - 120) % 360, s, int(v), int(a)
                # Assign directly to the pixel
                pixels[x][y] = color
        # The old way of closing a PixelArray object
        del pixels
        Scene.JojoScreenSurface = pygame.transform.rotozoom(screen_surface, 0, scaling_factor)

        pygame.mixer_music.load("./Assets/BGM/Jojo.mp3")
        pygame.mixer_music.set_volume(0.8)
        pygame.mixer_music.play(-1)
        Scene.paused = True
    
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
            case fparser.AbstractJojo:
                Scene.jojo()
            case fparser.AbstractCharaAction:
                Scene.characterBuffer[scriptLine.chara].set_expression(scriptLine.expression)

                if scriptLine.isUnknown:
                    Scene.characterBuffer[scriptLine.chara].displayName = "???"
                else:
                    Scene.characterBuffer[scriptLine.chara].reveal_name()

                Scene.characterBuffer[scriptLine.chara].say("...", -1)

                #print(Scene.lerpWeight)

                Scene.actionDuration = scriptLine.duration
                Scene.lerpWeightIncrement = 1 / (scriptLine.duration * FPS)

                Scene.characterBuffer[scriptLine.chara].action(scriptLine.action, Scene.lerpWeight)
            case fparser.AbstractCharaLine:
                Scene.characterBuffer[scriptLine.chara].set_expression(scriptLine.expression)

                if scriptLine.isUnknown:
                    Scene.characterBuffer[scriptLine.chara].displayName = "???"
                else:
                    Scene.characterBuffer[scriptLine.chara].reveal_name()
                
                Scene.characterBuffer[scriptLine.chara].say(scriptLine.line, scriptLine.sfxID)
            case fparser.AbstractNarratorLine:
                Scene.say(scriptLine.line, scriptLine.sfxID)
            case fparser.AbstractCG:
                Scene.loadCG(scriptLine.path)
            case fparser.IfStatement:
                Scene.testFor()
    
    def say(phrase : str, sfxID : int):
        text_box = TextWrapper.render_text_list(TextWrapper.wrap_text(phrase, SAY_FONT, UI.boxCharaText.size[0]), SAY_FONT, COLOR["$Narrator"])
        narrator_name = NAME_FONT.render("Narrator", True, COLOR["$Narrator"])
        textBuffer.append((narrator_name, UIBox.center(UI.boxCharaName, narrator_name)))    # (Surface, Rect)
        textBuffer.append((text_box, (180, 592)))   # (Surface, Rect)
        Scene.lastCharaDrawnSpeech = (text_box, (180, 592))

        if sfxID != -1: # If there's actually a sound to play
            if not Scene.hasAlreadyTalked:  # Plays the sound only once
                Scene.playVoiceline("$", sfxID)
                Scene.hasAlreadyTalked = True
                pygame.mixer_music.set_volume(BMG_BASE_VOLUME * 0.5)
        else:
            pygame.mixer_music.set_volume(BMG_BASE_VOLUME)  # You also need this here, otherwise, if you skip and there's no voiceline, the music stays at half volume
    
    def sayCG(phrase : str):
        text_box = TextWrapper.render_text_list(TextWrapper.wrap_text(phrase, SAY_FONT, UI.boxCharaText.size[0]), SAY_FONT, COLOR["$Narrator"])
        textBuffer.append((text_box, (180, 592)))   # (Surface, Rect)
        Scene.lastCharaDrawnSpeech = (text_box, (180, 592))
    
    def loadCG(path : str):
        Scene.cg = pygame.image.load(path).convert()
        Scene.sayCG("...")
    
    def loadMusic(loadFromChapter = False):
        # BGM
        Scene.previousMusicPath = Scene.musicPath   # Updates the variables here too, not just in Scene.advance()
        print(f"{Scene.previousMusicPath} //// {Scene.musicPath}")

        Scene.musicPath = Scene.data["MUSIC"]
        
        if loadFromChapter:
            if Scene.musicPath != None:
                if Scene.musicPath != "STOP":
                    print(f"SCENE.MUSICPATH : {Scene.musicPath}")
                    if Scene.musicPath != Scene.previousMusicPath: # If music changes
                        # Updates music
                        pygame.mixer_music.fadeout(1000)
                        pygame.mixer_music.load(Scene.musicPath)
                        pygame.mixer_music.play(-1)
                else:
                    pygame.mixer_music.fadeout(3000)
        else:
            if Scene.musicPath != "STOP":
                print(f"SCENE.MUSICPATH : {Scene.musicPath}")
                if Scene.musicPath != Scene.previousMusicPath: # If music changes
                    # Updates music
                    pygame.mixer_music.fadeout(1000)
                    pygame.mixer_music.load(Scene.musicPath)
                    pygame.mixer_music.play(-1)
            else:
                pygame.mixer_music.fadeout(3000)
    
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

    def loadSounds(chapter : str):
        # Narrator SFX
        if os.path.isdir(f"./Assets/SFX/{chapter}"):
            Scene.voicelines["$"] = [pygame.mixer.Sound(f"./Assets/SFX/{chapter}/{sfx}") for sfx in os.listdir(f"./Assets/SFX/{chapter}")]

        # Character Voicelines
        for chara in Scene.characterBuffer:
            if os.path.isdir(f"./Assets/Chara/{chara}/Voicelines/{chapter}"):
                Scene.voicelines[chara] = [pygame.mixer.Sound(f"./Assets/Chara/{chara}/Voicelines/{chapter}/{voiceline}") for voiceline in os.listdir(f"./Assets/Chara/{chara}/Voicelines/{chapter}")]
    
    def playSound(chara : str, sfxID : int):
        Scene.voicelines[chara][sfxID].set_volume(0.7)
        Scene.voicelines[chara][sfxID].play()
        #Scene.isDonePlayingSound = True
    
    def playVoiceline(chara : str, sfxID : int):
        Scene.currentVoiceline = Scene.voicelines[chara][sfxID]
        Scene.currentVoiceline.set_volume(0.7)
        Scene.voicelineChannel = Scene.currentVoiceline.play()
        #Scene.isDonePlayingVoiceline = True

    def loadCharacters():
        previousCharaList = Scene.characterBuffer.keys()
        abstractCharacters = Scene.data["CHARACTERS"]
        newCharaList = [newChara[0] for newChara in abstractCharacters]
        for oldChara in previousCharaList:
            if not oldChara in newCharaList:    # Do we need to free the character
                Scene.characterBuffer[oldChara].free()
        
        tmpCharacterBuffer = dict()
        
        for chara in abstractCharacters:
            print(type(chara))
            if chara[0] in previousCharaList:   # If it already exists, take the old one
                tmpCharacterBuffer[chara[0]] = Scene.characterBuffer[chara[0]]
                tmpCharacterBuffer[chara[0]].set_expression(chara[1])
                tmpCharacterBuffer[chara[0]].set_pos(POSITION[chara[2]])
            else:   # Otherwise, create a new Chara Object
                tmpCharacterBuffer[chara[0]] = Chara(chara[0], POSITION[chara[2]], COLOR[chara[0]], chara[1])
            print(f"CHARA {chara[0]}.{chara[1]} loaded")
        
        Scene.characterBuffer = tmpCharacterBuffer
        
        print(f"Active Character Objects : {Chara.count}")

    def parallaxEffect():
        max_offsetX = 10
        max_offsetY = 2
        screen_center = SCREEN_RECT.center

        mouse_pos = pygame.mouse.get_pos()
        for i in range(1, len(charaZBuffer)+1):
            charaZBuffer[i-1].apply_parallax(((screen_center[0] - mouse_pos[0]) * max_offsetX / screen_center[0])/i,((screen_center[1] - mouse_pos[1]) * max_offsetY / screen_center[1])/i)
        #print(f"{(mouse_pos[0] - screen_center[0]) * max_offset / screen_center[0]}, {(mouse_pos[1] - screen_center[1]) * max_offset / screen_center[1]}")

        # BG PARALLAX
        # Disabled because there are artifacts, even when resizing the image.
        # Scene.bg.apply_parallax(((screen_center[0] - mouse_pos[0]) * max_offsetX / screen_center[0])/(len(charaZBuffer)+1),((screen_center[1] - mouse_pos[1]) * max_offsetY / screen_center[1])/(len(charaZBuffer)+1))

    def checkCollisions():
        if len(Scene.choiceBuffer) != 0:
            for button in Scene.choiceBuffer:
                button.isClicked()
    def update():
        if not Scene.isJojo:
            # CHARA ACTIONS
            
            if not Scene.isCharaActionDone:
                Scene.lerpWeight = Scene.lerpWeight + Scene.lerpWeightIncrement
            
            if math.trunc(Scene.lerpWeight) >= 1:
                Scene.isCharaActionDone = True
                Scene.lerpWeight = math.trunc(Scene.lerpWeight)

            ## AUDIO
            if Scene.currentVoiceline != None:
                if not Scene.voicelineChannel.get_busy():   # Checks if it's busy playing the voiceline or if it's done
                    pygame.mixer_music.set_volume(BMG_BASE_VOLUME)  # If it's done, revert the BGM volume

            ## GRAPHICS
            # The background is always drawn first
            Scene.bg.update()
            
            if Scene.EnableParallax:
                Scene.parallaxEffect()

            # Then the characters (The first of the list is drawn last)
            for i in range(len(charaZBuffer)-1, -1, -1):
                charaZBuffer[i].update()
                #window.blit(chara.sprite, chara.pos)
            
            # Then the CG if there are any
            if Scene.cg != None:
                window.blit(Scene.cg, (0, 0))

            # Then the UI
            if not Scene.paused:
                Scene.readScript()
                Scene.previousScriptLineType = type(Scene.scriptBuffer[Scene.script_index])
            UI.update()
        else:
            window.blit(Scene.JojoScreenSurface, (0, 0))
            window.blit(Scene.ToBeContinued, (800, 600))

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
    name = str
    displayName = str
    expression = dict()
    sprite = None
    preParallaxPos = pygame.math.Vector2
    preActionPos = pygame.math.Vector2
    pos = pygame.math.Vector2
    rect = pygame.Rect
    size = 0.2
    rot = 0.0
    color = tuple()
    
    def __init__(self, name : str, initPos = (80, 20), color = (255, 255, 255), expression = "normal") -> None:
        self.name = name
        self.displayName = name
        if self.name == "Pucci" or self.name == "Dio" or self.name == "Assistant":
            self.size = 0.5
        self.expression = {sprite.split('.')[0][len(name)+1:] : pygame.transform.rotozoom(pygame.image.load(f"{self.charaFolder}{name}/Sprites/{sprite}").convert_alpha(), self.rot, self.size) for sprite in os.listdir(f"{self.charaFolder}{name}/Sprites")}
        self.color = color
        self.sprite = self.expression[expression]
        self.pos = pygame.math.Vector2(initPos[0], initPos[1])
        self.preParallaxPos = pygame.math.Vector2(initPos[0], initPos[1])
        self.preActionPos = self.preParallaxPos
        self.set_rect()
        
        charaZBuffer.append(self)        
        Chara.count += 1
    
    def __repr__(self):
        return self.name
    
    def update(self):
        window.blit(self.sprite, self.pos)
        #print(f"{self.name} || Pre : {self.preParallaxPos} | Post {self.pos}")
        self.pos = self.preParallaxPos
        self.preActionPos = self.preParallaxPos
    
    def apply_parallax(self, dx : float, dy : float):
        self.pos = self.preParallaxPos + pygame.Vector2(dx, dy)
        self.rect = round(self.pos.x), round(self.pos.y)
    
    def set_expression(self, expression : str):
        self.sprite = self.expression[expression]
    
    def set_pos(self, x : float, y : float):
        self.pos = pygame.math.Vector2(x, y)
        self.preParallaxPos = self.pos
        self.set_rect()
    
    def set_display_name(self, newName : str):
        self.displayName = newName
    
    def reveal_name(self):
        self.displayName = self.name
    
    def set_pos(self, pos : tuple):
        self.pos = pygame.math.Vector2(pos[0], pos[1])
        self.preParallaxPos = self.pos
        self.set_rect()
    
    def set_rect(self):
        self.rect = self.sprite.get_rect()
        self.rect.center = round(self.pos.x), round(self.pos.y)
    
    def move(self, dx : float, dy : float):
        self.pos += pygame.Vector2(dx, dy)
        self.rect = round(self.pos.x), round(self.pos.y)
    
    def action(self, action : str, weight = Scene.lerpWeight):
        match action:
            case "@enter_left":
                self.set_pos(vector_lerp(self.preActionPos, POSITION["chara1"], weight))
            case "@enter_leftb":
                self.set_pos(vector_lerp(self.preActionPos, POSITION["chara1b"], weight))
            case "@enter_right":
                self.set_pos(vector_lerp(self.preActionPos, POSITION["chara2"], weight))
            case "@enter_rightb":
                self.set_pos(vector_lerp(self.preActionPos, POSITION["chara2b"], weight))
            case "@enter_rightdio":
                self.set_pos(vector_lerp(self.preActionPos, POSITION["chara2dio"], weight))
            case "@leave_left":
                self.set_pos(vector_lerp(self.preActionPos, POSITION["out_left"], weight))
            case "@leave_right":
                self.set_pos(vector_lerp(self.preActionPos, POSITION["out_right"], weight))
            case "@go_chara1":
                self.set_pos(vector_lerp(self.preActionPos, POSITION["chara1"], weight))
            case "@go_chara1bump":
                self.set_pos(vector_lerp(self.preActionPos, POSITION["chara1bump"], weight))
    
    def say(self, phrase : str, sfxID : int):
        # The character that is currently speaking is drawn over everyone else, so, since we read the buffer backwards, we put the speaking character 1st in the list
        charaZBuffer.insert(0, charaZBuffer.pop(charaZBuffer.index(self)))

        text_box = TextWrapper.render_text_list(TextWrapper.wrap_text(phrase, SAY_FONT, UI.boxCharaText.size[0]), SAY_FONT, self.color)
        chara_name = NAME_FONT.render(self.displayName, True, self.color)
        textBuffer.append((chara_name, UIBox.center(UI.boxCharaName, chara_name)))    # (Surface, Rect)
        textBuffer.append((text_box, (180, 592)))   # (Surface, Rect)
        Scene.lastCharaDrawnSpeech = (text_box, (180, 592))

        if sfxID != -1: # If there's actually a sound to play
            if not Scene.hasAlreadyTalked:  # Plays the sound only once
                Scene.playVoiceline(self.name, sfxID)
                Scene.hasAlreadyTalked = True
                pygame.mixer_music.set_volume(BMG_BASE_VOLUME * 0.5)
        else:
            pygame.mixer_music.set_volume(BMG_BASE_VOLUME)  # You also need this here, otherwise, if you skip and there's no voiceline, the music stays at half volume
    
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