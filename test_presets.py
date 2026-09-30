import os
import json
import Cameras

def test_preset_lifecycle():
    user_dir = os.path.expanduser("~")
    preset_file = os.path.join(user_dir, "presets_config_abi.json")

    app = Cameras.CentralMonitoramento()

    # Set initial test grid configuration
    test_grid_1 = ["192.168.7.2", "192.168.7.3", "192.168.7.4", "192.168.7.20"] + ["0.0.0.0"] * 12
    app.grid_cameras = list(test_grid_1)

    # 1. Test Saving Preset
    preset_name_1 = "Predefinição Guarita"
    app._executar_salvamento_preset(preset_name_1)

    assert preset_name_1 in app.presets_salvos, "Preset 1 was not saved in memory"
    assert app.presets_salvos[preset_name_1] == test_grid_1, "Saved grid for Preset 1 does not match"

    # Verify JSON persistence
    with open(preset_file, "r", encoding="utf-8") as f:
        data_disk = json.load(f)
    assert preset_name_1 in data_disk, "Preset 1 was not saved to JSON file"

    # 2. Test Saving Second Preset
    test_grid_2 = ["192.168.7.21", "192.168.7.22"] + ["0.0.0.0"] * 14
    app.grid_cameras = list(test_grid_2)
    preset_name_2 = "Predefinição Estacionamento"
    app._executar_salvamento_preset(preset_name_2)

    assert preset_name_2 in app.presets_salvos, "Preset 2 was not saved in memory"

    # 3. Test Applying Preset
    app.aplicar_preset(preset_name_1)
    assert app.grid_cameras == test_grid_1, "Grid was not correctly loaded when applying Preset 1"

    # 4. Test Renaming Preset
    renamed_preset_1 = "Guarita Principal"
    app._executar_renomear_preset(preset_name_1, renamed_preset_1)

    assert preset_name_1 not in app.presets_salvos, "Old preset name still exists after renaming"
    assert renamed_preset_1 in app.presets_salvos, "Renamed preset does not exist in memory"
    assert app.presets_salvos[renamed_preset_1] == test_grid_1, "Renamed preset lost grid configuration"

    # Verify JSON persistence after rename
    with open(preset_file, "r", encoding="utf-8") as f:
        data_disk = json.load(f)
    assert preset_name_1 not in data_disk, "Old preset name still in JSON file"
    assert renamed_preset_1 in data_disk, "Renamed preset not found in JSON file"

    # 5. Test Deleting Preset
    app.excluir_preset(preset_name_2)
    assert preset_name_2 not in app.presets_salvos, "Preset 2 was not deleted from memory"

    with open(preset_file, "r", encoding="utf-8") as f:
        data_disk = json.load(f)
    assert preset_name_2 not in data_disk, "Preset 2 was not deleted from JSON file"

    # 6. Test UI references and tab switching
    app.mudar_aba_sidebar("Predefinições")
    assert renamed_preset_1 in app.preset_labels_referencia, "Preset label reference missing from UI dict"

    print("SUCCESS: All preset lifecycle tests passed!")
    app.destroy()

if __name__ == "__main__":
    test_preset_lifecycle()
