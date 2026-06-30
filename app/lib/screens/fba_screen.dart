import 'package:flutter/material.dart';
import '../models/models.dart';
import '../services/api_service.dart';
import '../theme/rf_colors.dart';
import '../theme/rf_glass.dart';
import '../utils/volume_button_service.dart';
import 'record_screen.dart';

class FbaScreen extends StatefulWidget {
  const FbaScreen({super.key});

  @override
  State<FbaScreen> createState() => _FbaScreenState();
}

class _FbaScreenState extends State<FbaScreen> {
  List<FbaShipment> _shipments = [];
  bool _loading = true;
  String? _error;

  Map<String, dynamic>? _selected;
  int _boxNumber = 1;
  final _boxCtrl = TextEditingController(text: '1');

  @override
  void initState() {
    super.initState();
    _loadShipments();
    VolumeButtonService().registerListener('fba_screen', (event) {
      if (!mounted) return;
      final route = ModalRoute.of(context);
      if (route == null || !route.isCurrent) return;
      if (event == 1 && _selected != null) _goRecord();
    });
  }

  @override
  void dispose() {
    VolumeButtonService().unregisterListener('fba_screen');
    _boxCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadShipments() async {
    setState(() { _loading = true; _error = null; });
    try {
      final list = await ApiService.getFbaShipments();
      if (mounted) setState(() { _shipments = list; _loading = false; });
    } catch (e) {
      if (mounted) setState(() { _error = e.toString(); _loading = false; });
    }
  }

  void _selectShipment(FbaShipment s) {
    setState(() { _selected = s.toJson(); });
  }

  void _goRecord() {
    if (_selected == null) return;
    Navigator.push(context, MaterialPageRoute(
      builder: (_) => RecordScreen(
        videoType: 'packing',
        fbaShipmentId: _selected!['shipment_id'] as String,
        fbaBoxNumber: _boxNumber,
      ),
    ));
  }

  @override
  Widget build(BuildContext context) {
    return RfGlassScaffold(
      appBar: const RfGlassAppBar(title: 'FBA Packing'),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _ErrorView(error: _error!, onRetry: _loadShipments)
              : _shipments.isEmpty
                  ? _EmptyView(onRetry: _loadShipments)
                  : _selected == null
                      ? _ShipmentList(shipments: _shipments, onSelect: _selectShipment)
                      : _BoxEntry(
                          shipment: _selected!,
                          boxNumber: _boxNumber,
                          controller: _boxCtrl,
                          onBoxChanged: (v) => setState(() => _boxNumber = v),
                          onBack: () => setState(() => _selected = null),
                          onRecord: _goRecord,
                        ),
    );
  }
}

class _ShipmentList extends StatelessWidget {
  final List<FbaShipment> shipments;
  final void Function(FbaShipment) onSelect;

  const _ShipmentList({required this.shipments, required this.onSelect});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Padding(
          padding: EdgeInsets.fromLTRB(24, 20, 24, 12),
          child: Text('Select Shipment', style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)),
        ),
        Expanded(
          child: ListView.separated(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            itemCount: shipments.length,
            separatorBuilder: (_, __) => const SizedBox(height: 8),
            itemBuilder: (_, i) {
              final s = shipments[i];
              final status = s.shipmentStatus;
              return RfGlassContainer(
                onTap: () => onSelect(s),
                padding: const EdgeInsets.all(16),
                child: Row(
                    children: [
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(s.shipmentId, style: const TextStyle(color: Color(0xFF58A6FF), fontFamily: 'monospace', fontSize: 13, fontWeight: FontWeight.bold)),
                            const SizedBox(height: 2),
                            if (s.shipmentName?.isNotEmpty == true)
                              Text(s.shipmentName!, style: const TextStyle(color: Colors.white70, fontSize: 12)),
                            const SizedBox(height: 4),
                            Row(
                              children: [
                                if (s.destinationFc?.isNotEmpty == true) ...[
                                  Text(s.destinationFc!, style: const TextStyle(color: Color(0xFF8B949E), fontSize: 11, fontFamily: 'monospace')),
                                  const Text(' · ', style: TextStyle(color: Color(0xFF8B949E), fontSize: 11)),
                                ],
                                Text(status, style: const TextStyle(color: Color(0xFF8B949E), fontSize: 11)),
                                const Text(' · ', style: TextStyle(color: Color(0xFF8B949E), fontSize: 11)),
                                Text('${s.unitCount} units', style: const TextStyle(color: Color(0xFF8B949E), fontSize: 11)),
                              ],
                            ),
                          ],
                        ),
                      ),
                      const Icon(Icons.chevron_right_rounded, color: Color(0xFF8B949E)),
                    ],
                ),
              );
            },
          ),
        ),
      ],
    );
  }
}

class _BoxEntry extends StatelessWidget {
  final Map<String, dynamic> shipment;
  final int boxNumber;
  final TextEditingController controller;
  final void Function(int) onBoxChanged;
  final VoidCallback onBack;
  final VoidCallback onRecord;

  const _BoxEntry({
    required this.shipment,
    required this.boxNumber,
    required this.controller,
    required this.onBoxChanged,
    required this.onBack,
    required this.onRecord,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          GestureDetector(
            onTap: onBack,
            child: Row(
              children: [
                const Icon(Icons.arrow_back_ios_new_rounded, color: Color(0xFF8B949E), size: 14),
                const SizedBox(width: 4),
                Text(shipment['shipment_id'] as String? ?? '', style: const TextStyle(color: Color(0xFF58A6FF), fontFamily: 'monospace', fontSize: 13)),
              ],
            ),
          ),
          const SizedBox(height: 32),
          const Text('Box Number', style: TextStyle(color: Color(0xFF8B949E), fontSize: 12, fontWeight: FontWeight.w600)),
          const SizedBox(height: 12),
          Row(
            children: [
              _CounterBtn(
                icon: Icons.remove,
                onTap: boxNumber > 1 ? () {
                  controller.text = (boxNumber - 1).toString();
                  onBoxChanged(boxNumber - 1);
                } : null,
              ),
              Expanded(
                child: TextField(
                  controller: controller,
                  keyboardType: TextInputType.number,
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: Colors.white, fontSize: 32, fontWeight: FontWeight.bold, fontFamily: 'monospace'),
                  decoration: const InputDecoration(border: InputBorder.none),
                  onChanged: (v) {
                    final n = int.tryParse(v);
                    if (n != null && n > 0) onBoxChanged(n);
                  },
                ),
              ),
              _CounterBtn(
                icon: Icons.add,
                onTap: () {
                  controller.text = (boxNumber + 1).toString();
                  onBoxChanged(boxNumber + 1);
                },
              ),
            ],
          ),
          const SizedBox(height: 8),
          const Text('Each box gets its own packing video', style: TextStyle(color: Color(0xFF4D5565), fontSize: 12), textAlign: TextAlign.center),
          const Spacer(),
          ElevatedButton.icon(
            onPressed: onRecord,
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.red,
              padding: const EdgeInsets.symmetric(vertical: 18),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
            icon: const Icon(Icons.videocam_rounded, size: 22),
            label: Text('Record Box $boxNumber', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
  }
}

class _CounterBtn extends StatelessWidget {
  final IconData icon;
  final VoidCallback? onTap;

  const _CounterBtn({required this.icon, this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: RfGlassContainer(
        blurEnabled: false,
        padding: EdgeInsets.zero,
        radius: RfRadius.button,
        tint: onTap != null ? RfColors.glassFill(0.16) : RfColors.glassFill(0.08),
        child: SizedBox(
          width: 52,
          height: 52,
          child: Icon(icon, color: onTap != null ? Colors.white : RfColors.border, size: 22),
        ),
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  final String error;
  final VoidCallback onRetry;
  const _ErrorView({required this.error, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.wifi_off_rounded, color: Color(0xFFFF7B72), size: 48),
            const SizedBox(height: 16),
            Text(error, style: const TextStyle(color: Color(0xFF8B949E)), textAlign: TextAlign.center),
            const SizedBox(height: 24),
            OutlinedButton(onPressed: onRetry, child: const Text('Retry')),
          ],
        ),
      ),
    );
  }
}

class _EmptyView extends StatelessWidget {
  final VoidCallback onRetry;
  const _EmptyView({required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.inventory_2_outlined, color: Color(0xFF8B949E), size: 48),
            const SizedBox(height: 16),
            const Text('No FBA shipments found', style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            const Text('Add a shipment in the dashboard or sync from SP-API.', style: TextStyle(color: Color(0xFF8B949E)), textAlign: TextAlign.center),
            const SizedBox(height: 24),
            OutlinedButton(onPressed: onRetry, child: const Text('Refresh')),
          ],
        ),
      ),
    );
  }
}
