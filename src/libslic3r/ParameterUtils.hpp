#ifndef slic3r_Parameter_Utils_hpp_
#define slic3r_Parameter_Utils_hpp_

#include <vector>
#include <map>

namespace Slic3r {
using LayerPrintSequence = std::pair<std::pair<int, int>, std::vector<int>>;
std::vector<LayerPrintSequence> get_other_layers_print_sequence(int sequence_nums, const std::vector<int> &sequence);
void get_other_layers_print_sequence(const std::vector<LayerPrintSequence> &customize_sequences, int &sequence_nums, std::vector<int> &sequence);

struct ExcludeAreaInfo
{
    std::vector<Pointfs> common;
    Pointfs              mirror;
    Pointfs              parallel;
    std::vector<Pointfs> head_specific;

    bool is_empty() const
    {
        return mirror.empty() && parallel.empty() &&
               std::all_of(common.begin(), common.end(), [](Pointfs const& pf) { return pf.empty(); }) &&
               std::all_of(head_specific.begin(), head_specific.end(), [](Pointfs const& pf) { return pf.empty(); });
    }

    bool operator==(ExcludeAreaInfo const& other) const
    {
        return common == other.common && mirror == other.mirror && parallel == other.parallel && head_specific == other.head_specific;
    }
    bool operator!=(ExcludeAreaInfo const& other) const { return !(*this == other); }

    void translate(const Vec2d& position)
    {
        auto translate_points = [&](Pointfs& pts) {
            for (auto& p : pts) {
                p = Vec2d(p.x() + position.x(), p.y() + position.y());
            }
        };

        for (auto& group : common)
            translate_points(group);

        translate_points(mirror);
        translate_points(parallel);

        for (auto& group : head_specific)
            translate_points(group);
    }

    void clear()
    {
        common.clear();
        mirror.clear();
        parallel.clear();
        head_specific.clear();
    }
};


} // namespace Slic3r

#endif // slic3r_Parameter_Utils_hpp_
