# ShadowRealms AI - Revised Model Strategy

## Resource Reality Check
**Your System:**
- NVIDIA 4080 Super with 16GB VRAM
- 64GB system RAM
- Running 6 models simultaneously = ~80GB+ VRAM needed
- **This won't work!** We need a much smarter approach.

## Revised Strategy: Dynamic Model Loading

### Core Concept
Instead of running all models simultaneously, we'll:
1. **Load models on-demand** based on task requirements
2. **Use 1-2 primary models** for most tasks
3. **Swap models** when specialized tasks are needed
4. **Cache frequently used models** in memory

### Recommended Model Setup

#### Primary Models (Always Available)
1. **MythoMakiseMerged-13B** (LM Studio)
   - **Purpose**: Primary roleplay, character creation, general RPG tasks
   - **VRAM**: ~8GB
   - **Usage**: 80% of all tasks

2. **llama3.2:3b** (Ollama)
   - **Purpose**: Fast responses, game mechanics, fallback
   - **VRAM**: ~2GB
   - **Usage**: 15% of tasks

#### Specialized Models (Load on Demand)
3. **meltemi-7b-v1-i1** (LM Studio)
   - **Purpose**: Greek language content only
   - **VRAM**: ~5GB
   - **Usage**: Only when Greek content needed

4. **command-r:35b** (Ollama)
   - **Purpose**: Complex storytelling, world-building
   - **VRAM**: ~20GB (too large for always-on)
   - **Usage**: Complex tasks only

### Smart Model Routing Strategy

#### Task Detection & Model Selection
```python
def select_model(task_type, context):
    if task_type == "greek_content":
        return load_model("meltemi-7b-v1-i1")
    elif task_type == "dice_rolling" or task_type == "combat":
        return load_model("llama3.2:3b")
    elif task_type == "complex_storytelling":
        return load_model("command-r:35b")
    else:
        return "mythomakisemerged-13b"  # Default
```

#### Model Loading Strategy
1. **Keep MythoMakiseMerged-13B loaded** (primary model)
2. **Load specialized models** only when needed
3. **Unload models** after 5 minutes of inactivity
4. **Preload models** based on campaign context

### Performance Optimizations

#### Memory Management
- **Model Swapping**: Unload unused models to free VRAM
- **Quantization**: Use 4-bit or 8-bit quantized models
- **Batch Processing**: Process multiple requests together

#### Response Time Optimization
- **Model Caching**: Keep frequently used models in memory
- **Async Loading**: Load models in background
- **Fallback System**: Use primary model if specialized model fails

### Revised Model Configuration

#### Phase 1: Core Setup (Immediate)
- **Primary**: MythoMakiseMerged-13B (always loaded)
- **Fallback**: llama3.2:3b (always loaded)
- **Total VRAM**: ~10GB (comfortable)

#### Phase 2: Specialized Features (Later)
- **Greek Support**: meltemi-7b-v1-i1 (load on demand)
- **Complex Tasks**: command-r:35b (load on demand)
- **Total VRAM**: ~15GB (with swapping)

### Implementation Plan

#### Step 1: Basic Model Router
```python
class SmartModelRouter:
    def __init__(self):
        self.primary_model = "mythomakisemerged-13b"
        self.loaded_models = {}
        self.model_timeouts = {}
    
    def get_response(self, prompt, task_type):
        model = self.select_model(task_type)
        if model not in self.loaded_models:
            self.load_model(model)
        return self.generate_response(model, prompt)
    
    def load_model(self, model_name):
        # Load model and start timeout
        pass
    
    def unload_model(self, model_name):
        # Unload model to free VRAM
        pass
```

#### Step 2: Model Lifecycle Management
- **Auto-unload**: Models unload after 5 minutes
- **Preloading**: Load models based on campaign context
- **Memory monitoring**: Track VRAM usage and swap when needed

#### Step 3: Performance Monitoring
- **Response times**: Track model response times
- **Memory usage**: Monitor VRAM usage
- **User experience**: Ensure <3 second responses

### Expected Performance
- **Primary tasks**: <2 seconds (MythoMakiseMerged-13B)
- **Specialized tasks**: <5 seconds (including model loading)
- **Greek content**: <8 seconds (model loading + generation)
- **Game mechanics**: <1 second (llama3.2:3b)

### Fallback Strategy
If any model fails:
1. **Try primary model** (MythoMakiseMerged-13B)
2. **Try fallback model** (command-r:35b)
3. **Return error** with helpful message

## Recommendation
**Start with 2 models** (MythoMakiseMerged-13B + command-r:35b) and add specialized models gradually as needed. This gives you:
- ✅ Responsive gameplay
- ✅ Manageable resource usage
- ✅ Room to grow
- ✅ Reliable performance

**Would you like me to implement this revised approach?**
