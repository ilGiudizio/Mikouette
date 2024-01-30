import time

chapter = dict()    # chapter[StoryBlockID] = StoryBlock
"""
{
    "SBID_1" : {
        "BG" : path,
        "CHARACTERS": ((Chara1, expression, startPos), (Chara2, expression, startPos)),
        "SCRIPT": (
            (Chara1, expression, "@CharacterAction"),
            (Chara1, expression, "Hello")
            ($Narrator, The Narrator doesn't speak in quotes)
        ),
        "GOTO": [
            (SBID, Transition) OR , (SBID, Label, {vars})
        ],
        "NEXT": (Chapter, SBID, transition)
    }
}
"""

class StoryBlock():
    bg = str()
    chara = list()
    script = list()
    
    def __init__(self, bg, chara, script) -> None:
        self.bg = bg
        self.chara = chara
        self.script = script

class AbstractNarratorLine():
    chara = "Narrator"
    line = str()
    
    def __init__(self, line : str) -> None:
        self.line = line

class AbstractCharaAction():
    chara = str()
    expression = str()
    action = str()
    
    def __init__(self, chara : str, expression : str, action : str) -> None:
        self.chara = chara
        self.expression = expression
        self.action = action

class AbstractCharaLine():
    chara = str()
    expression = str()
    line = str()
    
    def __init__(self, chara : str, expression : str, line : str) -> None:
        self.chara = chara
        self.expression = expression
        self.line = line
    
    def __repr__(self) -> str:
        return f"{self.chara} : *{self.expression}* {self.line}"
    
    def __str__(self) -> str:
        return f"{self.chara} : *{self.expression}* {self.line}"

class Parser():
    data = str()
    
    def loadChapter(path):
        with open(path, "r", encoding="utf-8") as file:
            Parser.data = file.read()
        
        Parser.parseChapter()
    
    def parseChapter():
        d = Parser.data
        
        tmpStoryBlocks = d.split("\n\n\n")
        tmpBG = str()   #Stores the latest Background
        tmpChara = str()    # Stores the current Character Name
        tmpExpression = dict()  # Stores each Character's latest expression
        
        for block in tmpStoryBlocks:
            tmpSBScript = []
            tmpSBCharacters = []
                        
            iSBID = 1
            tmpSBID = ""
            while block[iSBID] != "|":
                tmpSBID += block[iSBID]
                iSBID += 1
            
            chapter[tmpSBID] = {"BG" : str(), "CHARACTERS" : tuple(), "SCRIPT" : tuple(), "GOTO" : []}
            
            tmpActBlock = block.split("\n\n")
            for ab in tmpActBlock:
                tmpLines = ab.split("\n")
                for line in tmpLines:
                    line = line.strip(" ")
                    
                    match line[0]:
                        case "|":   # Skip the SBID
                            continue 
                        case "@":   # Action
                            tmpLineSplit = line.split("(")  # Skips the first character of the first part
                            tmpLineSplit[0] = tmpLineSplit[0][1:]
                            if len(tmpLineSplit) !=1 :
                                match tmpLineSplit[0]:
                                    case "BG":
                                        tmpBG = tmpLineSplit[1][:-1]    # Takes everything except for the ) at the end
                                    case "CHARACTERS":
                                        tmpCharaArgs = tmpLineSplit[1][:-1].split(";")  # Separates the Characters
                                        for charaArg in tmpCharaArgs:
                                            charaSubArgs = charaArg.split(",")  # Separates the Character.expression and the startPos
                                            subArg = charaSubArgs[0]
                                            charaAtoms = subArg.split(".")  # Separates the Character and the Expression
                                            tmpSBCharacters.append((charaAtoms[0].strip(" "), charaAtoms[1].strip(" "), charaSubArgs[1].strip(" "))) # <= (Chara1, expression, startPos)
                                            tmpExpression[charaAtoms[0].strip(" ")] = charaAtoms[1].strip(" ")
                                    case "GOTO":
                                        tmpGOTO = tmpLineSplit[1][:-1].split(",")
                                        chapter[tmpSBID]["GOTO"].append((tmpGOTO[0].strip(" "), tmpGOTO[1].strip(" ")))   # <= (SBID, transition)
                                    case "CHAPTER":
                                        tmpCHAPTER = tmpLineSplit[1][:-1].split(",")
                                        chapter[tmpSBID]["NEXT"] = (tmpCHAPTER[0].strip(" "), tmpCHAPTER[1].strip(" "), tmpCHAPTER[2].strip(" "))   # <= (Chapter, SBID, transition)
                                    case "CHOICE":
                                        tmpCHOICE = tmpLineSplit[1][:-1].split(";")
                                        for option in tmpCHOICE:
                                            option = option.split(":")
                                            tmpOLabel = option[0].strip(" ")
                                            tmpOParams = option[1].split(",")
                                            tmpOGOTO = tmpOParams.pop(0).strip(" ")
                                            if len(tmpOParams) != 0:    # aka if there are variables to assign
                                                tmpOVar = {}
                                                for param in tmpOParams:
                                                    param = param.split("=")
                                                    tmpOVar[param[0].strip(" ")] = param[1].strip(" ")
                                            chapter[tmpSBID]["GOTO"].append((tmpOGOTO, tmpOLabel, tmpOVar.copy())) # <= (SBID, Label, {vars})
                                        
                                        
                            else:   # Appends it to the script if it's a Character Action
                                tmpSBScript.append(AbstractCharaAction(tmpChara, tmpExpression[tmpChara], "@" + tmpLineSplit[0]))
                            
                        case "[":   # Character
                            tmpCharaSprite = line[1:-1].split(".")
                            if len(tmpCharaSprite) > 1: # aka if you change expression
                                tmpChara = tmpCharaSprite[0]
                                tmpExpression[tmpCharaSprite[0]] = tmpCharaSprite[1]    # updates the expression
                            tmpChara = tmpCharaSprite[0]
                            
                        case "\"":  # Speech Line
                            if tmpChara[0] == "$":  # In case it's the Narrator
                                tmpSBScript.append(AbstractNarratorLine(line[1:-1])) # line[1:-1] because the Narrator doesn't speak with ""
                            else:
                                tmpSBScript.append(AbstractCharaLine(tmpChara, tmpExpression[tmpChara], line))
                        case "#":   # Comment
                            continue
            
            chapter[tmpSBID]["BG"] = tmpBG
            chapter[tmpSBID]["CHARACTERS"] = tuple(tmpSBCharacters)
            chapter[tmpSBID]["SCRIPT"] = tuple(tmpSBScript)
                            
                
"""
startTime = time.perf_counter()   
            
Parser.loadChapter("./Story/chapter1.fvnc")
endTime = time.perf_counter()

print(chapter["1A"])
print(f"Parsed in {endTime - startTime:0.4f}s")
"""